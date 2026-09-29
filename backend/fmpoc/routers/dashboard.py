from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import Ctx, auth_ctx, get_db
from ..services import dashboard as svc

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), ctx: Ctx = Depends(auth_ctx)):
    if ctx.user.security_domain == "ADMINISTRATOR":
        return svc.administrator(db, ctx)
    if ctx.user.security_domain == "AUDITOR":
        return svc.auditor(db, ctx)
    return svc.financial(db, ctx)
