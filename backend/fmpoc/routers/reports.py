"""v1.2 reporting endpoints (CR-002). Read-only for all financial roles and Auditors; generation is audited."""
from __future__ import annotations

import datetime as dt
import os
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from .. import audit
from ..deps import Ctx, get_db, require
from ..models import FiscalYear
from ..services import reports as svc
from ..services.common import get_scoped

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _disposition(kind: str, name: str) -> str:
    ascii_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"


@router.get("/audit")
def audit_report(request: Request, fiscal_year_id: int = Query(...), bank_account_id: int | None = None,
                 include_void: bool = True, download: bool = False,
                 db: Session = Depends(get_db), ctx: Ctx = Depends(require("financial.view"))):
    fy = get_scoped(db, FiscalYear, fiscal_year_id, ctx, "Fiscal Year")
    path, fname, summary = svc.build_audit_report(db, ctx, request.app.state.settings, fy, bank_account_id, include_void)
    audit.record(db, ctx, "REPORT_GENERATED", "fiscal_year", fy.id, None,
                 {"report": "END_OF_YEAR_AUDIT", "bank_account_id": bank_account_id, "include_void": include_void,
                  **summary})
    db.commit()
    headers = {"Content-Disposition": _disposition("attachment" if download else "inline", fname),
               "Cache-Control": "private, no-store", "X-Frame-Options": "SAMEORIGIN",
               "Content-Security-Policy": "default-src 'none'; frame-ancestors 'self'"}
    return FileResponse(path, media_type="application/pdf", headers=headers,
                        background=BackgroundTask(lambda: os.path.exists(path) and os.unlink(path)))


@router.get("/fy-close")
def close_report(request: Request, fiscal_year_id: int = Query(...), download: bool = False,
                 db: Session = Depends(get_db), ctx: Ctx = Depends(require("financial.view"))):
    """v1.3 CR-008: Fiscal Year Close report (all accounts, VOID included, Fiscal Year documents up front)."""
    fy = get_scoped(db, FiscalYear, fiscal_year_id, ctx, "Fiscal Year")
    path, fname, summary = svc.build_audit_report(db, ctx, request.app.state.settings, fy, None, True, layout="close")
    audit.record(db, ctx, "REPORT_GENERATED", "fiscal_year", fy.id, None, {"report": "FISCAL_YEAR_CLOSE", **summary})
    db.commit()
    headers = {"Content-Disposition": _disposition("attachment" if download else "inline", fname),
               "Cache-Control": "private, no-store", "X-Frame-Options": "SAMEORIGIN",
               "Content-Security-Policy": "default-src 'none'; frame-ancestors 'self'"}
    return FileResponse(path, media_type="application/pdf", headers=headers,
                        background=BackgroundTask(lambda: os.path.exists(path) and os.unlink(path)))


@router.get("/entity-activity")
def entity_activity(bank_account_id: int | None = None, fiscal_year_id: int | None = None,
                    date_from: dt.date | None = None, date_to: dt.date | None = None, entity_id: int | None = None,
                    details: bool = False, format: Literal["json", "csv"] = "json",
                    db: Session = Depends(get_db), ctx: Ctx = Depends(require("financial.view"))):
    if fiscal_year_id is not None:
        fy = get_scoped(db, FiscalYear, fiscal_year_id, ctx, "Fiscal Year")
        date_from, date_to = date_from or fy.start_date, date_to or fy.end_date
    if date_from is None or date_to is None:
        from ..errors import validation
        raise validation("Provide date_from and date_to, or a fiscal_year_id.", "date_from")
    report = svc.entity_activity(db, ctx, account_id=bank_account_id, date_from=date_from, date_to=date_to,
                                 entity_id=entity_id, include_details=details or format == "csv")
    audit.record(db, ctx, "REPORT_GENERATED", "bank_account" if bank_account_id else "workspace",
                 bank_account_id or ctx.workspace_id, None,
                 {"report": "ENTITY_ACTIVITY", "date_from": date_from, "date_to": date_to, "entity_id": entity_id,
                  "format": format})
    db.commit()
    if format == "csv":
        name = f"entity-activity-{date_from}-to-{date_to}.csv"
        return Response(svc.entity_activity_csv(report), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": _disposition("attachment", name)})
    return report
