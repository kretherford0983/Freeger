"""v1.6.0 CR-033: Fundraiser module API (module switch, fundraisers)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import Ctx, get_db, require
from ..schemas import FundraiserBucketIn, FundraiserIn, FundraiserLineIn, FundraiserPreviewIn, ModulesIn
from ..services import fundraisers as svc

router = APIRouter(prefix="/api", tags=["fundraisers"])


@router.get("/system/modules")
def modules(db: Session = Depends(get_db), ctx: Ctx = Depends(require("modules.manage"))):
    return {"fundraisers": svc.module_enabled(db, ctx.workspace_id)}


@router.put("/system/modules")
def set_modules(body: ModulesIn, db: Session = Depends(get_db), ctx: Ctx = Depends(require("modules.manage"))):
    svc.set_module(db, ctx, body.fundraisers)
    db.commit()
    return {"fundraisers": svc.module_enabled(db, ctx.workspace_id)}


def viewer(db: Session = Depends(get_db), ctx: Ctx = Depends(require("fundraiser.view"))) -> Ctx:
    svc.require_module(db, ctx)
    return ctx


def manager(db: Session = Depends(get_db), ctx: Ctx = Depends(require("fundraiser.manage"))) -> Ctx:
    svc.require_module(db, ctx)
    return ctx


@router.get("/fundraisers")
def list_fundraisers(fiscal_year_id: int | None = None, upcoming: bool = False, include_archived: bool = False,
                     db: Session = Depends(get_db), ctx: Ctx = Depends(viewer)):
    return svc.list_out(db, ctx, fiscal_year_id, upcoming, include_archived)


@router.get("/fundraisers/budget-options")
def budget_options(start_date: dt.date = Query(...), end_date: dt.date | None = None,
                   db: Session = Depends(get_db), ctx: Ctx = Depends(manager)):
    return svc.budget_options(db, ctx, start_date, end_date or start_date)


@router.post("/fundraisers/preview")
def preview(body: FundraiserPreviewIn, db: Session = Depends(get_db), ctx: Ctx = Depends(manager)):
    return svc.preview(db, ctx, body.budget_ids, body.filter_text, body.filter_regex)


@router.post("/fundraisers", status_code=201)
def create(body: FundraiserIn, db: Session = Depends(get_db), ctx: Ctx = Depends(manager)):
    f = svc.create(db, ctx, body)
    db.commit()
    return svc.detail(db, ctx, f)


@router.get("/fundraisers/{fid}")
def get_one(fid: int, db: Session = Depends(get_db), ctx: Ctx = Depends(viewer)):
    return svc.detail(db, ctx, svc.get(db, ctx, fid))


@router.put("/fundraisers/{fid}")
def update(fid: int, body: FundraiserIn, db: Session = Depends(get_db), ctx: Ctx = Depends(manager)):
    f = svc.update(db, ctx, svc.get(db, ctx, fid), body)
    db.commit()
    return svc.detail(db, ctx, f)


@router.post("/fundraisers/{fid}/archive")
def archive(fid: int, db: Session = Depends(get_db), ctx: Ctx = Depends(manager)):
    f = svc.set_archived(db, ctx, svc.get(db, ctx, fid), True)
    db.commit()
    return svc.detail(db, ctx, f)


@router.post("/fundraisers/{fid}/restore")
def restore(fid: int, db: Session = Depends(get_db), ctx: Ctx = Depends(manager)):
    f = svc.set_archived(db, ctx, svc.get(db, ctx, fid), False)
    db.commit()
    return svc.detail(db, ctx, f)


@router.delete("/fundraisers/{fid}")
def delete(fid: int, db: Session = Depends(get_db), ctx: Ctx = Depends(manager)):
    svc.delete(db, ctx, svc.get(db, ctx, fid))
    db.commit()
    return {"deleted": True}


# ------------------------------------------------------------------ v1.6.1 CR-034: manage (Budget Manager, Register User)
def line_manager(db: Session = Depends(get_db), ctx: Ctx = Depends(require("fundraiser.lines"))) -> Ctx:
    svc.require_module(db, ctx)
    return ctx


@router.post("/fundraisers/{fid}/buckets", status_code=201)
def create_bucket(fid: int, body: FundraiserBucketIn, db: Session = Depends(get_db), ctx: Ctx = Depends(line_manager)):
    f = svc.get(db, ctx, fid)
    svc.create_bucket(db, ctx, f, body)
    db.commit()
    return svc.detail(db, ctx, f)


@router.put("/fundraisers/{fid}/buckets/{bucket_id}")
def update_bucket(fid: int, bucket_id: int, body: FundraiserBucketIn, db: Session = Depends(get_db),
                  ctx: Ctx = Depends(line_manager)):
    f = svc.get(db, ctx, fid)
    svc.update_bucket(db, ctx, f, svc.get_bucket(db, f, bucket_id), body)
    db.commit()
    return svc.detail(db, ctx, f)


@router.delete("/fundraisers/{fid}/buckets/{bucket_id}")
def delete_bucket(fid: int, bucket_id: int, db: Session = Depends(get_db), ctx: Ctx = Depends(line_manager)):
    f = svc.get(db, ctx, fid)
    svc.delete_bucket(db, ctx, f, svc.get_bucket(db, f, bucket_id))
    db.commit()
    return svc.detail(db, ctx, f)


@router.put("/fundraisers/{fid}/lines/{allocation_id}")
def set_line(fid: int, allocation_id: int, body: FundraiserLineIn, db: Session = Depends(get_db),
             ctx: Ctx = Depends(line_manager)):
    f = svc.get(db, ctx, fid)
    svc.set_line(db, ctx, f, allocation_id, body)
    db.commit()
    return svc.detail(db, ctx, f)
