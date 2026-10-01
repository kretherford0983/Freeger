"""v1.6.0 CR-033: optional Fundraiser module (plan: project doc claude/freedger-plan-1.6.md).

A fundraiser groups the activity of up to one income and one expense budget per Fiscal Year (at most two adjacent
Fiscal Years). Rules agreed with the product owner (2026-10-01):

- Event start/end dates are the physical dates of the event and are display only. Inclusion is by budget: every
  ACTIVE, live allocation to a selected budget (a parent includes all its children) that matches the optional
  description filter, whatever its transaction date.
- A fundraiser can be created as a "shell" (no budgets) as soon as it is agreed - before its Fiscal Year exists.
  Creating it (or moving its event dates) is refused only when the Fiscal Year covering the event start exists and
  is Closed.
- Budgets of a Fiscal Year may be chosen when that Fiscal Year exists, is not Closed and the event dates fall inside
  it or within 3 months of its start or end. Budgets of a Closed Fiscal Year are frozen.
- Filter: plain text = case-insensitive "contains"; with `filter_regex` a regular expression evaluated by RE2
  (linear time, so a pattern can never hang the server; no backreferences or look-arounds).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

import re2
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..errors import AppError, not_found, validation
from ..models import (Attachment, BankAccount, Budget, FiscalYear, Fundraiser, FundraiserBudget, RegisterTransaction,
                      TransactionAllocation, Workspace, utcnow)
from ..money import fmt
from . import bank_accounts as bank
from .common import add_months, budget_label, covering_fiscal_years, fy_brief, get_scoped

WINDOW_MONTHS = 3
MAX_FISCAL_YEARS = 2
FILTER_MAX = 200
KINDS = ("INCOME", "EXPENSE")


# ------------------------------------------------------------------ module switch
def module_enabled(db: Session, ws_id: int | None) -> bool:
    ws = db.get(Workspace, ws_id) if ws_id else None
    return bool(ws and ws.fundraisers_enabled)


def require_module(db: Session, ctx) -> None:
    if not module_enabled(db, ctx.workspace_id):
        raise AppError(404, "MODULE_DISABLED", "The Fundraiser module is not turned on.")


def set_module(db: Session, ctx, enabled: bool) -> bool:
    ws = db.get(Workspace, ctx.workspace_id)
    before = bool(ws.fundraisers_enabled)
    if before != enabled:
        ws.fundraisers_enabled = enabled
        audit.record(db, ctx, "MODULE_ENABLED" if enabled else "MODULE_DISABLED", "module", "fundraisers",
                     {"fundraisers_enabled": before}, {"fundraisers_enabled": enabled}, category="SECURITY")
    return enabled


# ------------------------------------------------------------------ filter
def compile_filter(text: str | None, is_regex: bool):
    """Returns a predicate over a description, or None when there is no filter. Raises 422 for a bad pattern."""
    text = (text or "").strip()
    if not text:
        return None
    if len(text) > FILTER_MAX:
        raise validation(f"The filter can be at most {FILTER_MAX} characters.", "filter_text")
    opts = re2.Options()
    opts.case_sensitive = False
    opts.log_errors = False
    if not is_regex:
        opts.literal = True
    try:
        pat = re2.compile(text, opts)
    except Exception:  # re2.error - message is engine-specific; keep it simple for users
        raise validation("The regular expression is not valid (backreferences and look-arounds are not supported).",
                         "filter_text") from None
    return lambda s: bool(s) and pat.search(s) is not None


# ------------------------------------------------------------------ Fiscal Year window rule
def in_window(fy: FiscalYear, start: dt.date, end: dt.date) -> bool:
    """The event lies inside the Fiscal Year or within 3 months of its start or end."""
    return start <= add_months(fy.end_date, WINDOW_MONTHS) and end >= add_months(fy.start_date, -WINDOW_MONTHS)


def _all_fys(db: Session, ws_id: int) -> list[FiscalYear]:
    return list(db.scalars(select(FiscalYear).where(FiscalYear.workspace_id == ws_id).order_by(FiscalYear.start_date)))


def eligible_fiscal_years(db: Session, ws_id: int, start: dt.date, end: dt.date) -> list[FiscalYear]:
    return [fy for fy in _all_fys(db, ws_id) if fy.status != "CLOSED" and in_window(fy, start, end)]


def _adjacent(db: Session, ws_id: int, a: FiscalYear, b: FiscalYear) -> bool:
    fys = _all_fys(db, ws_id)
    ia, ib = fys.index(a), fys.index(b)
    return abs(ia - ib) == 1


def check_event_dates(db: Session, ws_id: int, start: dt.date, end: dt.date) -> None:
    if end < start:
        raise validation("The event end date cannot be before its start date.", "end_date")
    closed = [fy for fy in covering_fiscal_years(db, ws_id, start) if fy.status == "CLOSED"]
    if closed:
        raise AppError(409, "FISCAL_YEAR_CLOSED",
                       f"The event date falls in {closed[0].display_name}, which is closed. Fundraisers can only be "
                       "set up while the Fiscal Year of the event is open.")


# ------------------------------------------------------------------ budgets
def leaf_ids(db: Session, b: Budget) -> list[int]:
    """A parent includes itself and all its children; a child is only itself."""
    if b.parent_budget_id is not None:
        return [b.id]
    kids = db.scalars(select(Budget.id).where(Budget.parent_budget_id == b.id))
    return [b.id, *kids]


def _parent(db: Session, b: Budget) -> Budget | None:
    return db.get(Budget, b.parent_budget_id) if b.parent_budget_id else None


def _has_explicit_children(db: Session, parent_id: int) -> bool:
    return db.scalar(select(Budget.id).where(Budget.parent_budget_id == parent_id, Budget.is_other.is_(False)).limit(1)) is not None


def budget_warnings(db: Session, b: Budget) -> list[dict]:
    out = []
    if b.is_other:
        p = _parent(db, b)
        if p is not None and _has_explicit_children(db, p.id):
            out.append({"code": "OTHER_BUDGET", "message": "An “Other” budget collects everything not planned in a "
                        "sub-budget. Items allocated to it that are not part of this fundraiser will affect the "
                        "validity of the fundraiser figures."})
    elif b.parent_budget_id is None and _has_explicit_children(db, b.id):
        out.append({"code": "PARENT_BUDGET", "message": "A parent budget includes all of its sub-budgets. Everything "
                    "allocated to any of them counts towards this fundraiser."})
    return out


def budget_brief(db: Session, b: Budget) -> dict:
    p = _parent(db, b)
    label = budget_label(p, None) if (b.is_other and p is not None and not _has_explicit_children(db, p.id)) else budget_label(b, p)
    return {"id": b.id, "label": label, "budget_type": b.budget_type, "fiscal_year_id": b.fiscal_year_id,
            "status": b.status, "warnings": budget_warnings(db, b)}


def budget_options(db: Session, ctx, start: dt.date, end: dt.date) -> list[dict]:
    """Per eligible Fiscal Year: the income and expense budgets that can be chosen (parents and sub-budgets)."""
    if end < start:
        return []
    out = []
    for fy in eligible_fiscal_years(db, ctx.workspace_id, start, end):
        budgets = list(db.scalars(select(Budget).where(Budget.fiscal_year_id == fy.id)
                                  .order_by(Budget.parent_code, Budget.child_code)))
        opts: dict[str, list] = {"INCOME": [], "EXPENSE": []}
        for p in (b for b in budgets if b.parent_budget_id is None and not b.is_budget_zero):
            kids = [k for k in budgets if k.parent_budget_id == p.id]
            explicit = [k for k in kids if not k.is_other]
            opts[p.budget_type].append({"id": p.id, "label": budget_label(p, None), "status": p.status,
                                        "level": 0, "warnings": budget_warnings(db, p)})
            if explicit:
                for k in [*explicit, *[k for k in kids if k.is_other]]:
                    opts[p.budget_type].append({"id": k.id, "label": budget_label(k, p), "status": k.status,
                                                "level": 1, "warnings": budget_warnings(db, k)})
        out.append({"fiscal_year": fy_brief(fy), "income": opts["INCOME"], "expense": opts["EXPENSE"]})
    return out


def _validate_budgets(db: Session, ctx, f: Fundraiser | None, start: dt.date, end: dt.date,
                      budget_ids: list[int]) -> list[tuple[Budget, FiscalYear]]:
    chosen: list[tuple[Budget, FiscalYear]] = []
    seen: set[tuple[int, str]] = set()
    existing = {fb.budget_id for fb in (f.budgets if f else [])}
    for bid in dict.fromkeys(budget_ids):
        b = db.get(Budget, bid)
        fy = db.get(FiscalYear, b.fiscal_year_id) if b else None
        if b is None or fy is None or fy.workspace_id != ctx.workspace_id:
            raise not_found("Budget")
        if b.is_budget_zero:
            raise validation("Budget 0 cannot be used for a fundraiser.", "budget_ids")
        key = (fy.id, b.budget_type)
        if key in seen:
            kind = "income" if b.budget_type == "INCOME" else "expense"
            raise validation(f"Only one {kind} budget can be chosen for {fy.display_name}.", "budget_ids")
        seen.add(key)
        if fy.status == "CLOSED":
            if bid not in existing:
                raise AppError(409, "FISCAL_YEAR_CLOSED", f"{fy.display_name} is closed; its budgets cannot be added.")
        elif not in_window(fy, start, end):
            raise validation(f"Budgets of {fy.display_name} can only be used when the event is inside that Fiscal Year "
                             f"or within {WINDOW_MONTHS} months of its start or end.", "budget_ids")
        chosen.append((b, fy))
    fys = list({fy.id: fy for _b, fy in chosen}.values())
    if len(fys) > MAX_FISCAL_YEARS:
        raise validation("A fundraiser can use budgets of at most two Fiscal Years.", "budget_ids")
    if len(fys) == 2 and not _adjacent(db, ctx.workspace_id, fys[0], fys[1]):
        raise validation("The two Fiscal Years of a fundraiser must follow each other.", "budget_ids")
    if f is not None:  # budgets of a closed Fiscal Year are frozen
        new_ids = {b.id for b, _fy in chosen}
        for fb in f.budgets:
            fy = db.get(FiscalYear, fb.fiscal_year_id)
            if fy.status == "CLOSED" and fb.budget_id not in new_ids:
                raise AppError(409, "FISCAL_YEAR_CLOSED", f"{fy.display_name} is closed; its budget for this "
                               "fundraiser cannot be removed or changed.")
    return chosen


# ------------------------------------------------------------------ CRUD
def snapshot(f: Fundraiser) -> dict:
    return {"id": f.id, "name": f.name, "description": f.description, "start_date": f.start_date.isoformat(),
            "end_date": f.end_date.isoformat(), "filter_text": f.filter_text, "filter_regex": bool(f.filter_regex),
            "budget_ids": [fb.budget_id for fb in f.budgets], "archived": f.archived_at is not None}


def _apply(db: Session, ctx, f: Fundraiser, body, creating: bool) -> None:
    start, end = body.start_date, body.end_date or body.start_date
    if creating or (start, end) != (f.start_date, f.end_date):
        check_event_dates(db, ctx.workspace_id, start, end)
    compile_filter(body.filter_text, bool(body.filter_regex))
    chosen = _validate_budgets(db, ctx, None if creating else f, start, end, body.budget_ids)
    if not creating:  # moving the event must keep frozen (closed-FY) budgets valid
        for fb in f.budgets:
            fy = db.get(FiscalYear, fb.fiscal_year_id)
            if fy.status == "CLOSED" and not in_window(fy, start, end):
                raise validation(f"The new dates are too far from {fy.display_name}, whose budget is part of this "
                                 "fundraiser and can no longer change.", "start_date")
    f.name, f.description = body.name, body.description or None
    f.start_date, f.end_date = start, end
    f.filter_text = (body.filter_text or "").strip() or None
    f.filter_regex = bool(body.filter_regex) and f.filter_text is not None
    f.updated_by_user_id = ctx.user.id
    want = {(fy.id, b.budget_type): b for b, fy in chosen}
    for fb in list(f.budgets):
        b = want.pop((fb.fiscal_year_id, fb.kind), None)
        if b is None:
            f.budgets.remove(fb)
        else:
            fb.budget_id = b.id
    for (fy_id, kind), b in want.items():
        f.budgets.append(FundraiserBudget(fiscal_year_id=fy_id, budget_id=b.id, kind=kind))


def create(db: Session, ctx, body) -> Fundraiser:
    f = Fundraiser(workspace_id=ctx.workspace_id, created_by_user_id=ctx.user.id, start_date=body.start_date,
                   end_date=body.end_date or body.start_date, name=body.name)
    _apply(db, ctx, f, body, creating=True)
    db.add(f)
    db.flush()
    audit.record(db, ctx, "FUNDRAISER_CREATED", "fundraiser", f.id, None, snapshot(f))
    return f


def update(db: Session, ctx, f: Fundraiser, body) -> Fundraiser:
    before = snapshot(f)
    _apply(db, ctx, f, body, creating=False)
    db.flush()
    after = snapshot(f)
    if after != before:
        audit.record(db, ctx, "FUNDRAISER_UPDATED", "fundraiser", f.id, before, after)
    return f


def set_archived(db: Session, ctx, f: Fundraiser, archived: bool) -> Fundraiser:
    if (f.archived_at is not None) == archived:
        return f
    before = snapshot(f)
    f.archived_at = utcnow() if archived else None
    f.archived_by_user_id = ctx.user.id if archived else None
    audit.record(db, ctx, "FUNDRAISER_ARCHIVED" if archived else "FUNDRAISER_RESTORED", "fundraiser", f.id, before,
                 snapshot(f))
    return f


def delete(db: Session, ctx, f: Fundraiser) -> None:
    """Allowed while nothing has been classified, excluded, bucketed or attached in the module (CR-034 adds those;
    in 1.6.0 a fundraiser holds only its settings). Otherwise: archive."""
    if any(fy.status == "CLOSED" for fy in _fys_of(db, f)):
        raise AppError(409, "FISCAL_YEAR_CLOSED", "A fundraiser using a closed Fiscal Year cannot be deleted; archive it.")
    audit.record(db, ctx, "FUNDRAISER_DELETED", "fundraiser", f.id, snapshot(f), None)
    db.delete(f)


def get(db: Session, ctx, fid: int) -> Fundraiser:
    return get_scoped(db, Fundraiser, fid, ctx, "Fundraiser")


# ------------------------------------------------------------------ derived figures
def _fys_of(db: Session, f: Fundraiser) -> list[FiscalYear]:
    ids = sorted({fb.fiscal_year_id for fb in f.budgets})
    return sorted((db.get(FiscalYear, i) for i in ids), key=lambda y: y.start_date)


def status_of(f: Fundraiser, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    if f.archived_at is not None:
        return "ARCHIVED"
    if today < f.start_date:
        return "PLANNED"
    if today <= f.end_date:
        return "IN_PROGRESS"
    return "ENDED"


def touched_fy_ids(db: Session, ws_id: int, f: Fundraiser, fys: list[FiscalYear] | None = None) -> set[int]:
    fys = fys if fys is not None else _all_fys(db, ws_id)
    ids = {fb.fiscal_year_id for fb in f.budgets}
    ids |= {fy.id for fy in fys if fy.start_date <= f.end_date and fy.end_date >= f.start_date}
    return ids


def _lines(db: Session, f: Fundraiser) -> tuple[list[dict], int]:
    """Included allocation lines (+ the number of lines in the budgets that the filter left out)."""
    pred = compile_filter(f.filter_text, bool(f.filter_regex))
    kind_of: dict[int, tuple[str, int]] = {}
    for fb in f.budgets:
        b = db.get(Budget, fb.budget_id)
        for lid in leaf_ids(db, b):
            kind_of[lid] = (fb.kind, fb.fiscal_year_id)
    if not kind_of:
        return [], 0
    q = (select(TransactionAllocation, RegisterTransaction)
         .join(RegisterTransaction, RegisterTransaction.id == TransactionAllocation.transaction_id)
         .where(TransactionAllocation.budget_id.in_(list(kind_of)), TransactionAllocation.removed_at.is_(None),
                RegisterTransaction.status == "ACTIVE")
         .order_by(RegisterTransaction.transaction_date, RegisterTransaction.id, TransactionAllocation.id))
    rows, skipped = [], 0
    for a, t in db.execute(q):
        if pred is not None and not pred(a.description or ""):
            skipped += 1
            continue
        kind, fy_id = kind_of[a.budget_id]
        rows.append({"a": a, "t": t, "kind": kind, "fiscal_year_id": fy_id})
    return rows, skipped


def preview(db: Session, ctx, budget_ids: list[int], filter_text: str | None, filter_regex: bool) -> dict:
    """Live preview for the create/edit form: how many lines the budgets hold and how many match the filter."""
    pred = compile_filter(filter_text, filter_regex)
    leafs: list[int] = []
    for bid in dict.fromkeys(budget_ids):
        b = db.get(Budget, bid)
        fy = db.get(FiscalYear, b.fiscal_year_id) if b else None
        if b is None or fy is None or fy.workspace_id != ctx.workspace_id:
            raise not_found("Budget")
        leafs += leaf_ids(db, b)
    total = matched = 0
    samples: list[str] = []
    if leafs:
        q = (select(TransactionAllocation.description)
             .join(RegisterTransaction, RegisterTransaction.id == TransactionAllocation.transaction_id)
             .where(TransactionAllocation.budget_id.in_(leafs), TransactionAllocation.removed_at.is_(None),
                    RegisterTransaction.status == "ACTIVE"))
        for (desc,) in db.execute(q):
            total += 1
            if pred is None or pred(desc or ""):
                matched += 1
            elif len(samples) < 5 and desc:
                samples.append(desc)
    shared = _shared_with(db, ctx.workspace_id, set(leafs), exclude_id=None)
    return {"total_lines": total, "matched_lines": matched, "unmatched_samples": samples,
            "shared_with": [{"id": x.id, "name": x.name} for x in shared]}


def _shared_with(db: Session, ws_id: int, leafs: set[int], exclude_id: int | None) -> list[Fundraiser]:
    if not leafs:
        return []
    out = []
    for other in db.scalars(select(Fundraiser).where(Fundraiser.workspace_id == ws_id, Fundraiser.archived_at.is_(None))):
        if other.id == exclude_id:
            continue
        theirs: set[int] = set()
        for fb in other.budgets:
            theirs |= set(leaf_ids(db, db.get(Budget, fb.budget_id)))
        if theirs & leafs:
            out.append(other)
    return out


def _money_totals(rows: list[dict]) -> dict:
    inc = sum(r["a"].amount_cents for r in rows if r["kind"] == "INCOME")
    exp = sum(r["a"].amount_cents for r in rows if r["kind"] == "EXPENSE")
    return {"income": inc, "expense": exp, "net": inc - exp}


def roi(income: int, expense: int) -> str | None:
    """Return on investment = net ÷ expense (None without expenses)."""
    return None if expense == 0 else f"{(income - expense) / expense:.4f}"


def notices(db: Session, ws_id: int, f: Fundraiser) -> list[dict]:
    out = []
    used = {fb.fiscal_year_id: set() for fb in f.budgets}
    for fb in f.budgets:
        used[fb.fiscal_year_id].add(fb.kind)
    fys = _all_fys(db, ws_id)
    if not f.budgets:
        out.append({"code": "NO_BUDGETS", "message": "No budgets selected yet. Select the income and/or expense budget "
                    "once the Fiscal Year and its budgets are set up."})
    if len(used) < MAX_FISCAL_YEARS:
        for fy in fys:
            if fy.id in used or fy.status == "CLOSED" or not in_window(fy, f.start_date, f.end_date):
                continue
            if used and not _adjacent(db, ws_id, fy, db.get(FiscalYear, next(iter(used)))):
                continue
            if f.budgets:
                out.append({"code": "FY_WITHOUT_BUDGET", "fiscal_year_id": fy.id,
                            "message": f"The event is within {WINDOW_MONTHS} months of {fy.display_name} — its budgets "
                                       "can also be selected for this fundraiser."})
        # a Fiscal Year within the window that is not set up yet (typically next year's)
        last_end = max((fy.end_date for fy in fys), default=None)
        if last_end is not None and add_months(f.end_date, WINDOW_MONTHS) > last_end:
            out.append({"code": "FUTURE_FY", "message": f"The event is within {WINDOW_MONTHS} months of a Fiscal Year "
                        "that is not set up yet — select its budgets once that Fiscal Year exists (Draft or later)."})
    for fb in f.budgets:
        b = db.get(Budget, fb.budget_id)
        for w in budget_warnings(db, b):
            out.append({**w, "budget_id": b.id})
    if f.filter_text:
        out.append({"code": "FILTER", "message": "A description filter is used: only lines whose description contains "
                    "the filter are included. Lines entered without it are left out, which affects the validity of the "
                    "figures."})
    leafs: set[int] = set()
    for fb in f.budgets:
        leafs |= set(leaf_ids(db, db.get(Budget, fb.budget_id)))
    shared = _shared_with(db, ws_id, leafs, exclude_id=f.id)
    if shared:
        out.append({"code": "SHARED_BUDGET", "message": "Another fundraiser uses the same budget(s): "
                    + ", ".join(x.name for x in shared) + ". Their totals overlap unless their filters separate them."})
    return out


def list_out(db: Session, ctx, fiscal_year_id: int | None, upcoming: bool, include_archived: bool) -> list[dict]:
    fys = _all_fys(db, ctx.workspace_id)
    q = select(Fundraiser).where(Fundraiser.workspace_id == ctx.workspace_id).order_by(Fundraiser.start_date, Fundraiser.name)
    if not include_archived:
        q = q.where(Fundraiser.archived_at.is_(None))
    out = []
    for f in db.scalars(q):
        touched = touched_fy_ids(db, ctx.workspace_id, f, fys)
        if upcoming:
            if touched:
                continue
        elif fiscal_year_id is not None and fiscal_year_id not in touched:
            continue
        rows, _skipped = _lines(db, f)
        t = _money_totals(rows)
        my_fys = [fy for fy in fys if fy.id in {fb.fiscal_year_id for fb in f.budgets}]
        out.append({**snapshot(f), "status": status_of(f), "fiscal_years": [fy_brief(y) for y in my_fys],
                    "income": fmt(t["income"]), "expense": fmt(t["expense"]), "net": fmt(t["net"]),
                    "has_budgets": bool(f.budgets)})
    return out


def detail(db: Session, ctx, f: Fundraiser) -> dict:
    rows, skipped = _lines(db, f)
    t = _money_totals(rows)
    fys = _fys_of(db, f)
    per_fy = []
    for fy in fys:
        sub = [r for r in rows if r["fiscal_year_id"] == fy.id]
        st = _money_totals(sub)
        per_fy.append({"fiscal_year": fy_brief(fy), "income": fmt(st["income"]), "expense": fmt(st["expense"]),
                       "net": fmt(st["net"]), "read_only": fy.status == "CLOSED"})
    accounts = {a.id: a for a in db.scalars(select(BankAccount).where(BankAccount.workspace_id == ctx.workspace_id))}
    t_ids = sorted({r["t"].id for r in rows})
    a_ids = [r["a"].id for r in rows]
    atts: dict[tuple[str, int], list[dict]] = defaultdict(list)
    if rows:
        q = select(Attachment).where(Attachment.active.is_(True),
                                     (Attachment.transaction_id.in_(t_ids)) | (Attachment.allocation_id.in_(a_ids)))
        for x in db.scalars(q.order_by(Attachment.id)):
            key = ("a", x.allocation_id) if x.allocation_id else ("t", x.transaction_id)
            atts[key].append({"id": x.id, "original_filename": x.original_filename, "mime_type": x.mime_type,
                              "size_bytes": x.size_bytes, "content_url": f"/api/attachments/{x.id}/content"})
    budget_cache: dict[int, dict] = {}
    lines = []
    for r in rows:
        a, tx = r["a"], r["t"]
        if a.budget_id not in budget_cache:
            budget_cache[a.budget_id] = budget_brief(db, db.get(Budget, a.budget_id))
        acct = accounts.get(tx.bank_account_id)
        ent = a.entity or tx.parent_entity
        lines.append({
            "allocation_id": a.id, "transaction_id": tx.id, "kind": r["kind"], "fiscal_year_id": r["fiscal_year_id"],
            "transaction_date": tx.transaction_date.isoformat(), "transaction_type": tx.transaction_type,
            "bank_account_id": tx.bank_account_id,
            "bank_account": f"{acct.account_name} - {bank.masked(acct)}" if acct else None,
            "entity": ent.display_name if ent else None, "description": a.description, "check_number": tx.check_number,
            "amount": fmt(a.amount_cents), "budget": budget_cache[a.budget_id]["label"],
            "cleared": tx.clear_date is not None,
            "attachments": atts.get(("t", tx.id), []) + atts.get(("a", a.id), []),
        })
    # cumulative income / expense from the first included transaction to the last (by transaction date)
    by_day: dict[str, list[int]] = {}
    for r in rows:
        d = r["t"].transaction_date.isoformat()
        by_day.setdefault(d, [0, 0])[0 if r["kind"] == "INCOME" else 1] += r["a"].amount_cents
    cum, inc, exp = [], 0, 0
    for d in sorted(by_day):
        inc += by_day[d][0]
        exp += by_day[d][1]
        cum.append({"date": d, "income": fmt(inc), "expense": fmt(exp), "net": fmt(inc - exp)})
    selected = []
    for fb in f.budgets:
        b = db.get(Budget, fb.budget_id)
        selected.append({**budget_brief(db, b), "kind": fb.kind, "fiscal_year": fy_brief(db.get(FiscalYear, fb.fiscal_year_id))})
    all_closed = bool(fys) and all(fy.status == "CLOSED" for fy in fys)
    if not fys:
        all_closed = any(fy.status == "CLOSED" for fy in covering_fiscal_years(db, ctx.workspace_id, f.start_date))
    return {
        **snapshot(f), "status": status_of(f), "fiscal_years": [fy_brief(y) for y in fys],
        "budgets": sorted(selected, key=lambda x: (x["fiscal_year"]["start_date"], x["kind"] != "INCOME")),
        "read_only": all_closed,
        "notices": notices(db, ctx.workspace_id, f),
        "totals": {"income": fmt(t["income"]), "expense": fmt(t["expense"]), "net": fmt(t["net"]),
                   "roi": roi(t["income"], t["expense"]), "classified": fmt(0), "excluded": fmt(0)},
        "per_fiscal_year": per_fy,
        "lines": lines, "filtered_out_lines": skipped,
        "cumulative": cum,
    }
