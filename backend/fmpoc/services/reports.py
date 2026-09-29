"""v1.2 reporting (change request CR-002).

* End of Year Audit report - a single printable PDF: cover and Fiscal Year budget, then every transaction of the
  year (all details, descriptions, notes, reviews) each immediately followed by its attachments (images rendered
  as pages, PDF attachments merged page-for-page), then the Fiscal Year supporting documents.
* Entity activity report - how much each entity deposited and withdrew for an account in a date range.

All user-controlled text is XML-escaped before it reaches reportlab's paragraph markup (prevents markup/<img>
injection); attachment bytes are read only through the application's generated storage paths and verified
against their recorded SHA-256.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import os
import tempfile
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..errors import validation
from ..models import (Attachment, BankAccount, Budget, Entity, FiscalYear, FiscalYearReview, RegisterTransaction,
                      TransactionAllocation, User, Workspace, utcnow)
from ..money import fmt
from . import bank_accounts as bank
from . import budgets as bsvc
from .attachments import path_for
from .common import budget_label
from .documentation import review as documentation_review
from .fiscal_years import closure_check

# --------------------------------------------------------------------------- fonts / styles
_FONT, _FONT_BOLD = "Helvetica", "Helvetica-Bold"
try:  # Bitstream Vera ships with reportlab and covers far more characters than the base-14 fonts
    import reportlab
    _fd = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    pdfmetrics.registerFont(TTFont("FMVera", os.path.join(_fd, "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("FMVeraBd", os.path.join(_fd, "VeraBd.ttf")))
    _FONT, _FONT_BOLD = "FMVera", "FMVeraBd"
except Exception:  # pragma: no cover - fall back to built-in fonts
    pass

_ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=_ss["Title"], fontName=_FONT_BOLD, fontSize=20, leading=24),
    "h1": ParagraphStyle("h1", parent=_ss["Heading1"], fontName=_FONT_BOLD, fontSize=15, leading=18, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=_ss["Heading2"], fontName=_FONT_BOLD, fontSize=12, leading=15, spaceAfter=4),
    "body": ParagraphStyle("b", parent=_ss["BodyText"], fontName=_FONT, fontSize=9, leading=11.5),
    "small": ParagraphStyle("s", parent=_ss["BodyText"], fontName=_FONT, fontSize=7.5, leading=9.5),
    "cell": ParagraphStyle("c", parent=_ss["BodyText"], fontName=_FONT, fontSize=7.5, leading=9),
    "cellr": ParagraphStyle("cr", parent=_ss["BodyText"], fontName=_FONT, fontSize=7.5, leading=9, alignment=TA_RIGHT),
    "cellb": ParagraphStyle("cb", parent=_ss["BodyText"], fontName=_FONT_BOLD, fontSize=7.5, leading=9),
}
PAGE_W, PAGE_H = letter
MARGIN = 0.6 * inch
FRAME_W = PAGE_W - 2 * MARGIN
FRAME_H = PAGE_H - 2 * MARGIN - 0.3 * inch


def P(text, style="body") -> Paragraph:
    """Paragraph from *untrusted* text: always escaped, newlines preserved."""
    t = escape("" if text is None else str(text)).replace("\n", "<br/>")
    return Paragraph(t, S[style])


def PM(markup: str, style="body") -> Paragraph:
    """Paragraph from trusted markup built by this module (callers escape any user values)."""
    return Paragraph(markup, S[style])


def money(c: int | str | None) -> str:
    if c is None:
        return ""
    v = c if isinstance(c, str) else fmt(c)
    neg = v.startswith("-")
    i, d = v.lstrip("-").split(".")
    return f"{'-' if neg else ''}${int(i):,}.{d}"


def _grid(data, widths, header_rows=1, zebra=True, extra=None) -> Table:
    t = Table(data, colWidths=widths, repeatRows=header_rows)
    style = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9aa3ad")),
             ("BACKGROUND", (0, 0), (-1, header_rows - 1), colors.HexColor("#e8ecf1")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if zebra:
        for r in range(header_rows, len(data)):
            if (r - header_rows) % 2:
                style.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f6f8fa")))
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def _kv(rows: list[tuple[str, object]], w1=1.45 * inch) -> Table:
    data = [[PM(f"<b>{escape(k)}</b>", "cell"), P(v, "cell")] for k, v in rows]
    t = Table(data, colWidths=[w1, FRAME_W - w1])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
                           ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


# --------------------------------------------------------------------------- PDF assembly
@dataclass
class _Doc:
    """Accumulates PDF parts in order and records a footer label for every resulting page."""
    writer: PdfWriter = field(default_factory=PdfWriter)
    labels: list[str] = field(default_factory=list)

    def add_flowables(self, flowables: list, label: str) -> None:
        buf = io.BytesIO()
        SimpleDocTemplate(buf, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN,
                          bottomMargin=MARGIN + 0.25 * inch, title="End of Year Audit Report").build(flowables)
        buf.seek(0)
        for page in PdfReader(buf).pages:
            self.writer.add_page(page)
            self.labels.append(label)

    def add_pdf(self, data: bytes, label: str) -> int:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        n = 0
        for page in reader.pages:
            self.writer.add_page(page)
            self.labels.append(label)
            n += 1
        return n

    def finish(self, path: str, title: str) -> None:
        total = len(self.writer.pages)
        for i, page in enumerate(self.writer.pages):
            w, h = float(page.mediabox.width), float(page.mediabox.height)
            buf = io.BytesIO()
            c = rl_canvas.Canvas(buf, pagesize=(w, h))
            c.setFont(_FONT, 7)
            c.setFillColor(colors.HexColor("#444444"))
            c.drawString(18, 10, f"{title}  ·  {self.labels[i]}"[:160])
            c.drawRightString(w - 18, 10, f"Page {i + 1} of {total}")
            c.save()
            buf.seek(0)
            page.merge_page(PdfReader(buf).pages[0])
        self.writer.add_metadata({"/Title": title, "/Producer": "Financial Management POC"})
        with open(path, "wb") as fh:
            self.writer.write(fh)


def _attachment_bytes(settings, a: Attachment) -> tuple[bytes | None, str]:
    try:
        with open(path_for(settings, a), "rb") as fh:
            data = fh.read()
    except OSError:
        return None, "stored file missing"
    if hashlib.sha256(data).hexdigest() != a.sha256:
        return data, "SHA-256 MISMATCH - stored file differs from the uploaded file"
    return data, "SHA-256 verified"


def _image_flowables(data: bytes, caption: list) -> list:
    with PILImage.open(io.BytesIO(data)) as im:
        w, h = im.size
    avail_h = FRAME_H - 1.1 * inch
    scale = min(FRAME_W / w, avail_h / h, 1.0 if w < 200 else 10)
    return [PageBreak(), *caption, Spacer(1, 6), Image(io.BytesIO(data), width=w * scale, height=h * scale)]


def _attachment_caption(label: str, a: Attachment, integrity: str, users: dict[int, str]) -> list:
    return [PM(f"<b>{escape(label)}</b>", "h2"),
            _kv([("File", a.original_filename), ("Type / size", f"{a.mime_type} · {a.size_bytes:,} bytes"),
                 ("Uploaded", f"{a.uploaded_at:%Y-%m-%d %H:%M} UTC by {users.get(a.uploaded_by_user_id, '?')}"),
                 ("SHA-256", f"{a.sha256}  ({integrity})")])]


# --------------------------------------------------------------------------- data selection
def audit_transactions(db: Session, ws_id: int, fy: FiscalYear, account_id: int | None,
                       include_void: bool) -> list[RegisterTransaction]:
    """Transactions dated in the Fiscal Year plus any (cross-FY) transaction allocated to its budgets."""
    alloc_ids = select(TransactionAllocation.transaction_id).join(Budget, Budget.id == TransactionAllocation.budget_id) \
        .where(Budget.fiscal_year_id == fy.id, TransactionAllocation.removed_at.is_(None))
    q = select(RegisterTransaction).where(
        RegisterTransaction.workspace_id == ws_id,
        or_(RegisterTransaction.transaction_date.between(fy.start_date, fy.end_date),
            RegisterTransaction.id.in_(alloc_ids)))
    if account_id:
        q = q.where(RegisterTransaction.bank_account_id == account_id)
    if not include_void:
        q = q.where(RegisterTransaction.status == "ACTIVE")
    txns = list(db.scalars(q))
    accts = {a.id: a for a in db.scalars(select(BankAccount).where(BankAccount.workspace_id == ws_id))}
    txns.sort(key=lambda t: (accts[t.bank_account_id].account_name.lower(), t.bank_account_id, t.transaction_date,
                             t.entry_timestamp, t.id))
    return txns


def _attachments_for(db: Session, t: RegisterTransaction) -> tuple[list[Attachment], dict[int, list[Attachment]], list[Attachment]]:
    alloc_ids = [a.id for a in t.allocations]
    rows = list(db.scalars(select(Attachment).where(or_(Attachment.transaction_id == t.id,
                                                        Attachment.allocation_id.in_(alloc_ids or [-1])))
                           .order_by(Attachment.id)))
    parent = [a for a in rows if a.transaction_id == t.id and a.active]
    by_alloc: dict[int, list[Attachment]] = {}
    for a in rows:
        if a.allocation_id and a.active:
            by_alloc.setdefault(a.allocation_id, []).append(a)
    removed = [a for a in rows if not a.active]
    return parent, by_alloc, removed


# --------------------------------------------------------------------------- End of Year Audit report
def build_audit_report(db: Session, ctx, settings, fy: FiscalYear, account_id: int | None = None,
                       include_void: bool = True) -> tuple[str, str, dict]:
    """Returns (temp file path, download filename, summary). Caller deletes the file."""
    ws = db.get(Workspace, ctx.workspace_id)
    users = {u.id: u.username for u in db.scalars(select(User).where(User.workspace_id == ctx.workspace_id))}
    accts = {a.id: a for a in db.scalars(select(BankAccount).where(BankAccount.workspace_id == ctx.workspace_id))}
    if account_id is not None and account_id not in accts:
        raise validation("Bank Account not found.", "bank_account_id")
    title = f"End of Year Audit Report — {fy.display_name} — {ws.name}"
    doc = _Doc()
    tree = bsvc.tree(db, fy)
    check = closure_check(db, fy)
    txns = audit_transactions(db, ctx.workspace_id, fy, account_id, include_void)
    doc_items = {i["transaction_id"]: i for i in documentation_review(db, fy)}
    fy_atts = list(db.scalars(select(Attachment).where(Attachment.fiscal_year_id == fy.id, Attachment.active.is_(True))
                              .order_by(Attachment.id)))
    now = utcnow()

    # ---- cover + budget
    f: list = [PM(escape(ws.name), "h1"), PM("End of Year Audit Report", "title"), Spacer(1, 6),
               _kv([("Fiscal Year", f"{fy.display_name} ({fy.start_date} – {fy.end_date})"),
                    ("Status", fy.status.title()),
                    ("Approved", f"{fy.approved_at:%Y-%m-%d %H:%M} UTC by {users.get(fy.approved_by_user_id, '?')}"
                     if fy.approved_at else "—"),
                    ("Closed", f"{fy.closed_at:%Y-%m-%d %H:%M} UTC by {users.get(fy.closed_by_user_id, '?')}"
                     if fy.closed_at else "—"),
                    ("Accounts", accts[account_id].account_name + " - " + bank.masked(accts[account_id])
                     if account_id else "All register-enabled accounts"),
                    ("Transactions", f"{len(txns)} ({'including' if include_void else 'excluding'} VOID)"),
                    ("Generated", f"{now:%Y-%m-%d %H:%M} UTC by {ctx.user.username}")]),
               Spacer(1, 10), PM("Fiscal Year Budget", "h1")]
    qn = [q["name"] for q in tree["quarters"]]
    for label, rows, summ in (("Income", tree["income"], tree["income_summary"]),
                              ("Expense", tree["expense"], tree["expense_summary"])):
        f.append(PM(f"{label} budgets", "h2"))
        data = [[PM("<b>Budget</b>", "cell"), PM("<b>Status</b>", "cell"), PM("<b>Amount</b>", "cellr"),
                 *[PM(f"<b>{q}</b>", "cellr") for q in qn], PM("<b>Actual</b>", "cellr"), PM("<b>Remaining</b>", "cellr")]]
        for r in rows:
            for x, indent in [(r, ""), *[(c, "    ") for c in r["children"]]]:
                data.append([P(indent + x["label"], "cell"), P(x["state"]["label"], "cell"), P(money(x["amount"]), "cellr"),
                             *[P(money(q), "cellr") for q in x["quarters"]], P(money(x["actual"]), "cellr"),
                             P(money(x["remaining"]), "cellr")])
        data.append([PM("<b>Total</b>", "cell"), P("", "cell"), PM(f"<b>{money(summ['amount'])}</b>", "cellr"),
                     *[P(money(q), "cellr") for q in summ["quarters"]], PM(f"<b>{money(summ['actual'])}</b>", "cellr"),
                     PM(f"<b>{money(summ['remaining'])}</b>", "cellr")])
        if len(data) == 2:
            data.insert(1, [P(f"No {label.lower()} budgets.", "cell")] + [""] * 8)
        f.append(_grid(data, [2.0 * inch, 1.05 * inch, 0.75 * inch] + [0.52 * inch] * 4 + [0.7 * inch, 0.72 * inch]))
        f.append(Spacer(1, 6))
    if tree["budget_zero"]:
        b0 = tree["budget_zero"]
        f.append(P(f"Protected Budget 0 (non-budget activity such as transfers): inflows {money(b0.get('inflow'))}, "
                   f"outflows {money(b0.get('outflow'))}.", "small"))
    f += [Spacer(1, 8), PM("Closure readiness and review", "h2")]
    items = [f"Blocker: {b['message']}" for b in check["blockers"]] + [f"Warning: {w['message']}" for w in check["warnings"]]
    f += [P(x, "small") for x in (items or ["No blockers or warnings."])]
    # transaction index
    f += [PageBreak(), PM("Transaction index", "h1"),
          P("Each transaction below starts on a new page and is immediately followed by all of its attachments.", "small"),
          Spacer(1, 4)]
    idx = [[PM(f"<b>{h}</b>", "cell") for h in ("#", "Date", "Account", "Type", "Entity", "Amount", "Status", "Att.")]]
    att_cache = {}
    for t in txns:
        att_cache[t.id] = _attachments_for(db, t)
        n_att = len(att_cache[t.id][0]) + sum(len(v) for v in att_cache[t.id][1].values())
        a = accts[t.bank_account_id]
        idx.append([P(t.id, "cell"), P(t.transaction_date, "cell"), P(f"{a.account_name} {bank.masked(a)}", "cell"),
                    P(t.transaction_type.title(), "cell"), P(t.parent_entity.display_name if t.parent_entity else "", "cell"),
                    P(money(t.total_cents), "cellr"), P(t.status + ("" if t.clear_date or t.status == "VOID" else " (uncleared)"), "cell"),
                    P(n_att if n_att else ("none*" if t.no_attachment else "0"), "cell")])
    if len(idx) == 1:
        f.append(P("No transactions for this Fiscal Year.", "body"))
    else:
        f.append(_grid(idx, [0.45 * inch, 0.75 * inch, 1.75 * inch, 0.8 * inch, 1.55 * inch, 0.85 * inch, 0.85 * inch,
                             0.4 * inch]))
    f.append(P("* marked 'no attachment will be provided'", "small"))
    doc.add_flowables(f, "Budget and index")

    # ---- transactions, each followed by its attachments
    for t in txns:
        a = accts[t.bank_account_id]
        label = f"Transaction #{t.id}"
        parent_atts, by_alloc, removed = att_cache[t.id]
        live = t.live_allocations
        flow: list = [PM(f"Transaction #{t.id} — {escape(t.transaction_type.title())} — {escape(money(t.total_cents))}"
                         + (" — <font color='#b3261e'>VOID</font>" if t.status == "VOID" else ""), "h1")]
        kv = [("Account", f"{a.account_name} - {bank.masked(a)}"),
              ("Transaction date", t.transaction_date), ("Clear/Post date", t.clear_date or "Uncleared"),
              ("Entry timestamp", f"{t.entry_timestamp:%Y-%m-%d %H:%M:%S} UTC (by {users.get(t.created_by_user_id, '?')})"),
              ("Entity", f"{t.parent_entity.display_name} ({t.parent_entity.entity_number})" if t.parent_entity else "—"),
              ("Check number", t.check_number or "—"), ("Status", t.status)]
        if t.status == "VOID":
            kv.append(("Void", f"{t.void_reason} — {t.voided_at:%Y-%m-%d %H:%M} UTC by {users.get(t.voided_by_user_id, '?')}"
                       if t.voided_at else t.void_reason))
        if t.transfer_group:
            other = db.scalar(select(RegisterTransaction).where(RegisterTransaction.transfer_group == t.transfer_group,
                                                                RegisterTransaction.id != t.id))
            if other is not None:
                oa = accts[other.bank_account_id]
                kv.append(("Transfer", f"{'to' if t.transaction_type == 'WITHDRAWAL' else 'from'} {oa.account_name} "
                                       f"{bank.masked(oa)} (transaction #{other.id})"))
        if t.no_attachment:
            kv.append(("Documentation", f"Marked 'no attachment will be provided': {t.no_attachment_reason or '(no reason)'}"))
        di = doc_items.get(t.id)
        if di and di["category"] == "MISSING_ATTACHMENTS":
            kv.append(("Documentation review", "WARNING: supporting attachments missing"))
        kv.append(("Notes", t.notes or "—"))
        flow += [_kv(kv), Spacer(1, 6), PM("Allocations", "h2")]
        rows = [[PM(f"<b>{h}</b>", "cell") for h in ("Fiscal Year / Budget", "Entity", "Invoice #", "Description",
                                                     "Notes", "Amount", "Review")]]
        for al in live:
            b = al.budget
            parent = db.get(Budget, b.parent_budget_id) if b.parent_budget_id else None
            lbl = budget_label(parent, None) if b.is_other and parent and not bsvc.children_of(db, parent)[0] else budget_label(b, parent)
            fyb = db.get(FiscalYear, b.fiscal_year_id)
            revs = db.scalars(select(FiscalYearReview).where(FiscalYearReview.transaction_allocation_id == al.id)).all()
            rows.append([P(f"{fyb.display_name} / {lbl}", "cell"), P(al.entity.display_name if al.entity else "", "cell"),
                         P(al.invoice_number or "", "cell"), P(al.description or "", "cell"), P(al.notes or "", "cell"),
                         P(money(al.amount_cents), "cellr"),
                         P("; ".join(f"{r.category} {r.status}" + (f" ({r.review_note})" if r.review_note else "") for r in revs), "cell")])
        flow.append(_grid(rows, [1.55 * inch, 1.0 * inch, 0.7 * inch, 1.45 * inch, 1.2 * inch, 0.7 * inch, 0.7 * inch]))
        ordered: list[tuple[str, Attachment]] = [("transaction", x) for x in parent_atts]
        for al in live:
            ordered += [(f"allocation {al.id}", x) for x in by_alloc.get(al.id, [])]
        flow += [Spacer(1, 6), PM("Attachments", "h2")]
        if ordered:
            flow.append(_grid([[PM(f"<b>{h}</b>", "cell") for h in ("#", "File", "Attached to", "Type", "SHA-256")]] +
                              [[P(i + 1, "cell"), P(x.original_filename, "cell"), P(k, "cell"), P(x.mime_type, "cell"),
                                P(x.sha256, "small")] for i, (k, x) in enumerate(ordered)],
                              [0.3 * inch, 2.0 * inch, 1.0 * inch, 1.0 * inch, 3.0 * inch]))
        else:
            flow.append(P("No attachments." + (" Marked 'no attachment will be provided'." if t.no_attachment else ""), "small"))
        if removed:
            flow.append(P("Removed attachments (retained in history, not reproduced): " + ", ".join(
                f"{x.original_filename} (removed {x.removed_at:%Y-%m-%d})" for x in removed), "small"))
        # images are appended inside this part; PDFs are merged right after, in attachment order
        pending_pdf: list[tuple[str, Attachment, bytes, str]] = []

        def flush_part():
            doc.add_flowables(flow, label)
            flow.clear()

        for i, (k, x) in enumerate(ordered):
            cap_label = f"{label} · Attachment {i + 1} of {len(ordered)}"
            data, integrity = _attachment_bytes(settings, x)
            cap = _attachment_caption(cap_label, x, integrity, users)
            if data is None:
                flow += [PageBreak(), *cap, P(f"Attachment content unavailable: {integrity}.", "body")]
                continue
            if x.mime_type.startswith("image/"):
                try:
                    flow += _image_flowables(data, cap)
                except Exception:
                    flow += [PageBreak(), *cap, P("Image could not be rendered.", "body")]
                continue
            # PDF: caption page is part of the flowables, then the attachment pages are merged in order
            flow += [PageBreak(), *cap, P("The attachment's pages follow.", "small")]
            flush_part()
            try:
                doc.add_pdf(data, f"{cap_label}: {x.original_filename}")
            except Exception:
                doc.add_flowables([*cap, P("This PDF could not be embedded (malformed or protected). The stored file "
                                           "is retained and identified by its SHA-256 above.", "body")], cap_label)
        if flow:
            flush_part()
        del pending_pdf

    # ---- Fiscal Year supporting documentation
    ff: list = [PM("Fiscal Year supporting documentation", "h1")]
    if not fy_atts:
        ff.append(P("No Fiscal Year supporting attachments.", "body"))
    doc.add_flowables(ff, "Supporting documentation")
    for i, x in enumerate(fy_atts):
        cap_label = f"FY document {i + 1} of {len(fy_atts)}"
        data, integrity = _attachment_bytes(settings, x)
        cap = _attachment_caption(cap_label, x, integrity, users)
        if data is None:
            doc.add_flowables([*cap, P(f"Attachment content unavailable: {integrity}.", "body")], cap_label)
        elif x.mime_type.startswith("image/"):
            doc.add_flowables(_image_flowables(data, cap)[1:], cap_label)
        else:
            doc.add_flowables([*cap, P("The document's pages follow.", "small")], cap_label)
            try:
                doc.add_pdf(data, f"{cap_label}: {x.original_filename}")
            except Exception:
                doc.add_flowables([P("This PDF could not be embedded.", "body")], cap_label)

    fd, path = tempfile.mkstemp(prefix="fmpoc-audit-", suffix=".pdf")
    os.close(fd)
    doc.finish(path, title)
    fname = f"{fy.display_name}-end-of-year-audit-report.pdf"
    return path, fname, {"transactions": len(txns), "pages": len(doc.labels)}


# --------------------------------------------------------------------------- Entity activity report
def entity_activity(db: Session, ctx, *, account_id: int | None, date_from: dt.date, date_to: dt.date,
                    entity_id: int | None, include_details: bool) -> dict:
    if date_to < date_from:
        raise validation("date_to must be on or after date_from.", "date_to")
    accts = {a.id: a for a in db.scalars(select(BankAccount).where(BankAccount.workspace_id == ctx.workspace_id))}
    if account_id is not None and account_id not in accts:
        raise validation("Bank Account not found.", "bank_account_id")
    q = (select(TransactionAllocation, RegisterTransaction)
         .join(RegisterTransaction, RegisterTransaction.id == TransactionAllocation.transaction_id)
         .where(RegisterTransaction.workspace_id == ctx.workspace_id, RegisterTransaction.status == "ACTIVE",
                TransactionAllocation.removed_at.is_(None),
                RegisterTransaction.transaction_date.between(date_from, date_to))
         .order_by(RegisterTransaction.transaction_date, RegisterTransaction.id, TransactionAllocation.id))
    if account_id is not None:
        q = q.where(RegisterTransaction.bank_account_id == account_id)
    groups: dict[str, dict] = {}
    for al, t in db.execute(q).all():
        if t.transfer_group:
            key, ent = "transfers", None
        else:
            ent = al.entity or t.parent_entity
            if ent is not None and ent.is_system:
                ent = None
            key = f"e{ent.id}" if ent else "none"
        if entity_id is not None and (ent is None or ent.id != entity_id):
            continue
        g = groups.setdefault(key, {
            "key": key, "entity": None if ent is None else {"id": ent.id, "entity_number": ent.entity_number,
                                                            "display_name": ent.display_name, "active": ent.active},
            "label": ent.display_name if ent else ("(Transfers between accounts)" if key == "transfers" else "(No entity)"),
            "deposits": 0, "withdrawals": 0, "deposit_txns": set(), "withdrawal_txns": set(), "lines": []})
        if t.transaction_type == "DEPOSIT":
            g["deposits"] += al.amount_cents
            g["deposit_txns"].add(t.id)
        else:
            g["withdrawals"] += al.amount_cents
            g["withdrawal_txns"].add(t.id)
        if include_details:
            a = accts[t.bank_account_id]
            g["lines"].append({"transaction_id": t.id, "transaction_date": t.transaction_date.isoformat(),
                               "account": f"{a.account_name} - {bank.masked(a)}", "type": t.transaction_type,
                               "description": al.description, "invoice_number": al.invoice_number,
                               "check_number": t.check_number, "amount": fmt(al.amount_cents),
                               "cleared": t.clear_date is not None})
    rows = []
    for g in groups.values():
        rows.append({"key": g["key"], "entity": g["entity"], "label": g["label"], "deposits": fmt(g["deposits"]),
                     "withdrawals": fmt(g["withdrawals"]), "net": fmt(g["deposits"] - g["withdrawals"]),
                     "deposit_count": len(g["deposit_txns"]), "withdrawal_count": len(g["withdrawal_txns"]),
                     "lines": g["lines"] if include_details else None})
    order = {"none": 1, "transfers": 2}
    rows.sort(key=lambda r: (order.get(r["key"], 0), r["label"].lower()))
    entity_rows = [r for r in rows if r["key"] != "transfers"]
    tot_d = sum(int(round(float(r["deposits"]) * 100)) for r in entity_rows)
    tot_w = sum(int(round(float(r["withdrawals"]) * 100)) for r in entity_rows)
    acct = accts.get(account_id) if account_id else None
    return {"account": {"id": acct.id, "label": f"{acct.account_name} - {bank.masked(acct)}"} if acct else None,
            "date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "rows": rows,
            "totals": {"deposits": fmt(tot_d), "withdrawals": fmt(tot_w), "net": fmt(tot_d - tot_w),
                       "note": "Totals exclude transfers between accounts."},
            "generated_at": utcnow().isoformat() + "Z"}


def _csv_safe(v) -> str:
    """Neutralise spreadsheet formula injection in exported text (=, +, -, @ prefixes)."""
    s = "" if v is None else str(v)
    if s and s[0] in "=+-@\t\r" and not _is_number(s):
        return "'" + s
    return s


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def entity_activity_csv(report: dict) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Entity", "Entity Number", "Deposits", "Deposit transactions", "Withdrawals", "Withdrawal transactions",
                "Net", "Account", "From", "To"])
    acct = report["account"]["label"] if report["account"] else "All accounts"
    for r in report["rows"]:
        w.writerow([_csv_safe(r["label"]), r["entity"]["entity_number"] if r["entity"] else "", r["deposits"],
                    r["deposit_count"], r["withdrawals"], r["withdrawal_count"], r["net"], _csv_safe(acct),
                    report["date_from"], report["date_to"]])
    if any(r["lines"] for r in report["rows"]):
        w.writerow([])
        w.writerow(["Entity", "Transaction #", "Date", "Account", "Type", "Description", "Invoice #", "Check #", "Amount"])
        for r in report["rows"]:
            for ln in r["lines"] or []:
                w.writerow([_csv_safe(r["label"]), ln["transaction_id"], ln["transaction_date"], _csv_safe(ln["account"]),
                            ln["type"], _csv_safe(ln["description"]), _csv_safe(ln["invoice_number"]),
                            _csv_safe(ln["check_number"]), ln["amount"]])
    return out.getvalue()


__all__ = ["build_audit_report", "entity_activity", "entity_activity_csv", "KeepTogether", "Entity"]
