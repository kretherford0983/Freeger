"""v1.2 Fiscal Year documentation review (change request CR-005).

Lists ACTIVE transactions that affect a Fiscal Year and either
  * lack supporting attachments ("MISSING_ATTACHMENTS"), or
  * are explicitly marked "no attachment will be provided" ("NO_ATTACHMENT_MARKED").
These are Fiscal Year review *warnings*; they never block approval or closure.

Attachment rule (as specified):
  * single allocation: missing when neither the transaction nor its allocation has an attachment;
  * split transaction: missing when (the parent has 0 attachments and not every child has one)
    or (no child has an attachment). If every child has an attachment the parent needs none.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Attachment, BankAccount, Budget, FiscalYear, RegisterTransaction, TransactionAllocation
from ..money import fmt
from .common import entity_brief


def split_is_documented(parent_count: int, child_counts: list[int]) -> bool:
    """Single place encoding the split-transaction documentation rule (see module docstring)."""
    every_child = all(c > 0 for c in child_counts)
    any_child = any(c > 0 for c in child_counts)
    if every_child:
        return True
    if parent_count == 0:
        return False
    return any_child


def is_documented(parent_count: int, child_counts: list[int]) -> bool:
    if len(child_counts) <= 1:
        return parent_count + sum(child_counts) > 0
    return split_is_documented(parent_count, child_counts)


def _counts(db: Session, txn_ids: list[int], alloc_ids: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    tc: dict[int, int] = {}
    ac: dict[int, int] = {}
    if txn_ids:
        for tid, n in db.execute(select(Attachment.transaction_id, func.count(Attachment.id))
                                 .where(Attachment.transaction_id.in_(txn_ids), Attachment.active.is_(True))
                                 .group_by(Attachment.transaction_id)):
            tc[tid] = n
    if alloc_ids:
        for aid, n in db.execute(select(Attachment.allocation_id, func.count(Attachment.id))
                                 .where(Attachment.allocation_id.in_(alloc_ids), Attachment.active.is_(True))
                                 .group_by(Attachment.allocation_id)):
            ac[aid] = n
    return tc, ac


def applicable_transactions(db: Session, fy: FiscalYear) -> list[RegisterTransaction]:
    """ACTIVE transactions with at least one live allocation to a budget of this Fiscal Year."""
    ids = db.scalars(select(RegisterTransaction.id).distinct()
                     .join(TransactionAllocation, TransactionAllocation.transaction_id == RegisterTransaction.id)
                     .join(Budget, Budget.id == TransactionAllocation.budget_id)
                     .where(Budget.fiscal_year_id == fy.id, RegisterTransaction.status == "ACTIVE",
                            TransactionAllocation.removed_at.is_(None))).all()
    if not ids:
        return []
    return list(db.scalars(select(RegisterTransaction).where(RegisterTransaction.id.in_(ids))
                           .order_by(RegisterTransaction.transaction_date, RegisterTransaction.id)))


def review(db: Session, fy: FiscalYear) -> list[dict]:
    txns = applicable_transactions(db, fy)
    alloc_ids = [a.id for t in txns for a in t.live_allocations]
    tc, ac = _counts(db, [t.id for t in txns], alloc_ids)
    accounts: dict[int, BankAccount] = {}
    items = []
    for t in txns:
        allocs = t.live_allocations
        parent = tc.get(t.id, 0)
        children = [ac.get(a.id, 0) for a in allocs]
        if t.no_attachment:
            category = "NO_ATTACHMENT_MARKED"
        elif not is_documented(parent, children):
            category = "MISSING_ATTACHMENTS"
        else:
            continue
        acct = accounts.get(t.bank_account_id) or db.get(BankAccount, t.bank_account_id)
        accounts[t.bank_account_id] = acct
        from .bank_accounts import masked
        items.append({
            "transaction_id": t.id, "category": category, "transaction_date": t.transaction_date.isoformat(),
            "transaction_type": t.transaction_type, "total": fmt(t.total_cents), "is_split": len(allocs) > 1,
            "is_transfer": t.transfer_group is not None,
            "bank_account": {"id": acct.id, "label": f"{acct.account_name} - {masked(acct)}"},
            "entity": entity_brief(t.parent_entity), "parent_attachment_count": parent,
            "allocations_without_attachment": [a.id for a, c in zip(allocs, children) if c == 0],
            "allocation_count": len(allocs),
            "no_attachment_reason": t.no_attachment_reason,
            "description": "; ".join(a.description for a in allocs if a.description)[:300] or None,
        })
    return items


def closure_warnings(db: Session, fy: FiscalYear) -> list[dict]:
    items = review(db, fy)
    out = []
    missing = [i["transaction_id"] for i in items if i["category"] == "MISSING_ATTACHMENTS"]
    marked = [i["transaction_id"] for i in items if i["category"] == "NO_ATTACHMENT_MARKED"]
    if missing:
        out.append({"code": "MISSING_ATTACHMENTS", "message": f"{len(missing)} transaction(s) have no supporting attachments.",
                    "transaction_ids": missing})
    if marked:
        out.append({"code": "NO_ATTACHMENT_MARKED",
                    "message": f"{len(marked)} transaction(s) are marked 'no attachment will be provided'.",
                    "transaction_ids": marked})
    return out
