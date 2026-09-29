from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Ctx, get_db, require
from ..models import User
from ..schemas import PasswordResetIn, UserCreateIn, UserUpdateIn
from ..services import users as svc

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(db: Session = Depends(get_db), ctx: Ctx = Depends(require("users.view"))):
    return [svc.out(u) for u in db.scalars(select(User).where(User.workspace_id == ctx.workspace_id).order_by(User.username))]


@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db), ctx: Ctx = Depends(require("users.view"))):
    return svc.out(svc.get(db, ctx, user_id))


@router.post("", status_code=201)
def create_user(body: UserCreateIn, db: Session = Depends(get_db), ctx: Ctx = Depends(require("users.manage"))):
    u = svc.create(db, ctx, body)
    db.commit()
    return svc.out(u)


@router.patch("/{user_id}")
def update_user(user_id: int, body: UserUpdateIn, db: Session = Depends(get_db), ctx: Ctx = Depends(require("users.manage"))):
    u = svc.update(db, ctx, svc.get(db, ctx, user_id), body)
    db.commit()
    return svc.out(u)


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, body: PasswordResetIn, db: Session = Depends(get_db),
                   ctx: Ctx = Depends(require("users.manage"))):
    svc.reset_password(db, ctx, svc.get(db, ctx, user_id), body.new_password)
    db.commit()
    return {"ok": True}
