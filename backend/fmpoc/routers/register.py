from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import Ctx, get_db, require
from ..errors import AppError
from ..models import BankAccount, FiscalYear, FiscalYearReview, RegisterTransaction, TransactionAllocation
from ..schemas import NoteIn, ReviewResolveIn, TransactionCreateIn, TransactionUpdateIn, VoidDateIn, VoidIn
from ..services import register as svc
from ..services.common import get_scoped

router = APIRouter(prefix="/api", tags=["register"])


@router.get("/register")
def register_view(
    bank_account_id: int | None = None,
    fiscal_year_id: int | None = None,
    transaction_type: Literal["DEPOSIT", "WITHDRAWAL"] | None = None,
    status: Literal["cleared", "uncleared", "void", "active"] | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    search: str | None = Query(None, max_length=200),
    sort: Literal["transaction_date", "entry_timestamp", "amount", "check_number", "clear_date"] = "transaction_date",
    direction: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db), ctx: Ctx = Depends(require("financial.view")),
):
    if bank_account_id is None:  # default: Primary register-enabled account
        acct = db.scalar(select(BankAccount).where(BankAccount.workspace_id == ctx.workspace_id,
                                                   BankAccount.is_primary.is_(True)))
        if acct is None:
            acct = db.scalar(select(BankAccount).where(BankAccount.workspace_id == ctx.workspace_id,
                                                       BankAccount.register_enabled.is_(True))
                             .order_by(BankAccount.status, BankAccount.id))
        if acct is None:
            return {"bank_account": None, "transactions": []}
    else:
        acct = get_scoped(db, BankAccount, bank_account_id, ctx, "Bank Account")
    if not acct.register_enabled:
        raise AppError(422, "NOT_REGISTER_ENABLED", "The Bank Account is not register-enabled.")
    fy = get_scoped(db, FiscalYear, fiscal_year_id, ctx, "Fiscal Year") if fiscal_year_id else None
    return svc.register_view(db, ctx, acct, fiscal_year=fy, txn_type=transaction_type, status=status,
                             date_from=date_from, date_to=date_to, search=search, sort=sort, direction=direction)


@router.get("/transactions/{txn_id}")
def get_txn(txn_id: int, db: Session = Depends(get_db), ctx: Ctx = Depends(require("financial.view"))):
    return svc.out(db, svc.get(db, ctx, txn_id))


@router.post("/transactions", status_code=201)
def create_txn(body: TransactionCreateIn, db: Session = Depends(get_db), ctx: Ctx = Depends(require("transaction.manage"))):
    t = svc.create(db, ctx, body)
    db.commit()
    return svc.out(db, t)


@router.patch("/transactions/{txn_id}")
def update_txn(txn_id: int, body: TransactionUpdateIn, db: Session = Depends(get_db),
               ctx: Ctx = Depends(require("transaction.manage"))):
    t = svc.update(db, ctx, svc.get(db, ctx, txn_id), body)
    db.commit()
    return svc.out(db, t)


@router.post("/transactions/{txn_id}/void")
def void_txn(txn_id: int, body: VoidIn, db: Session = Depends(get_db), ctx: Ctx = Depends(require("transaction.manage"))):
    t = svc.void(db, ctx, svc.get(db, ctx, txn_id), body.reason, body.confirm_irreversible)
    db.commit()
    return svc.out(db, t)


@router.post("/transactions/{txn_id}/void-date")
def correct_void_date(txn_id: int, body: VoidDateIn, db: Session = Depends(get_db),
                      ctx: Ctx = Depends(require("transaction.manage"))):
    t = svc.correct_void_date(db, ctx, svc.get(db, ctx, txn_id), body.transaction_date, body.fiscal_year_id, body.reason)
    db.commit()
    return svc.out(db, t)


@router.post("/transactions/{txn_id}/notes")
def add_note(txn_id: int, body: NoteIn, db: Session = Depends(get_db), ctx: Ctx = Depends(require("transaction.manage"))):
    t = svc.add_note(db, ctx, svc.get(db, ctx, txn_id), body.note)
    db.commit()
    return svc.out(db, t)


@router.get("/fiscal-year-reviews")
def list_reviews(status: Literal["PENDING", "REVIEWED", "REASSIGNED", "all"] = "PENDING",
                 fiscal_year_id: int | None = None,
                 db: Session = Depends(get_db), ctx: Ctx = Depends(require("financial.view"))):
    q = (select(FiscalYearReview)
         .join(TransactionAllocation, TransactionAllocation.id == FiscalYearReview.transaction_allocation_id)
         .join(RegisterTransaction, RegisterTransaction.id == TransactionAllocation.transaction_id)
         .where(FiscalYearReview.workspace_id == ctx.workspace_id))
    if status != "all":
        q = q.where(FiscalYearReview.status == status)
    if status == "PENDING":
        q = q.where(RegisterTransaction.status == "ACTIVE", TransactionAllocation.removed_at.is_(None))
    items = [svc.review_out(db, r) for r in db.scalars(q.order_by(FiscalYearReview.id))]
    if fiscal_year_id:
        items = [i for i in items if i["budget"]["fiscal_year"]["id"] == fiscal_year_id
                 or (i["natural_fiscal_year"] or {}).get("id") == fiscal_year_id]
    return items


@router.post("/fiscal-year-reviews/{review_id}/confirm")
def confirm_review(review_id: int, body: ReviewResolveIn, db: Session = Depends(get_db),
                   ctx: Ctx = Depends(require("review.resolve"))):
    r = svc.resolve_review(db, ctx, svc.get_review(db, ctx, review_id), body.note)
    db.commit()
    return svc.review_out(db, r)
