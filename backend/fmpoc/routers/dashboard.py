from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import Ctx, auth_ctx, get_db, require
from ..models import FiscalYear
from ..services import charts as charts_svc
from ..services.common import get_scoped
from ..services import dashboard as svc

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), ctx: Ctx = Depends(auth_ctx)):
    if ctx.user.security_domain == "ADMINISTRATOR":
        return svc.administrator(db, ctx)
    if ctx.user.security_domain == "AUDITOR":
        return svc.auditor(db, ctx)
    return svc.financial(db, ctx)


@router.get("/dashboard/charts")
def dashboard_charts(fiscal_year_id: int = Query(...), db: Session = Depends(get_db),
                     ctx: Ctx = Depends(require("financial.view"))):
    """v1.4.1 CR-020: chart data for one Fiscal Year (financial roles and Auditors)."""
    return charts_svc.data(db, ctx, get_scoped(db, FiscalYear, fiscal_year_id, ctx, "Fiscal Year"))
