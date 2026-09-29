"""Reporting (v1.2 CR-002; v1.3 CR-008).

* End of Year Audit report - a single printable PDF: title, Fiscal Year review, budgets, then every transaction of
  the year with its attachments reproduced beneath it.
* Fiscal Year Close report - the same, with the Fiscal Year documents (approval, audit signoff, other) placed after
  the review and before the budgets; generated on demand and automatically when the Fiscal Year is closed.
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
from xml.sax.saxutils import escape

from PIL import Image as PILImage
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
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
    "h3": ParagraphStyle("h3", parent=_ss["BodyText"], fontName=_FONT, fontSize=9, leading=11.5),
    "metak": ParagraphStyle("mk", parent=_ss["BodyText"], fontName=_FONT_BOLD, fontSize=10, leading=13),
    "metav": ParagraphStyle("mv", parent=_ss["BodyText"], fontName=_FONT, fontSize=10, leading=13),
    "cover_org": ParagraphStyle("co", parent=_ss["Title"], fontName=_FONT, fontSize=16, leading=20),
    "cover_title": ParagraphStyle("ct", parent=_ss["Title"], fontName=_FONT_BOLD, fontSize=28, leading=34),
    "cover_sub": ParagraphStyle("cs", parent=_ss["Title"], fontName=_FONT, fontSize=14, leading=19, spaceAfter=0),
    "cellb": ParagraphStyle("cb", parent=_ss["BodyText"], fontName=_FONT_BOLD, fontSize=7.5, leading=9),
}
PAGE_W, PAGE_H = letter
MARGIN = 0.6 * inch
FRAME_W = PAGE_W - 2 * MARGIN


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


def _kv(rows: list[tuple[str, object]], w1=1.45 * inch, style="cell") -> Table:
    data = [[PM(f"<b>{escape(k)}</b>", style), P(v, style)] for k, v in rows]
    t = Table(data, colWidths=[w1, FRAME_W - 12 - w1])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2),
                           ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    return t


# --------------------------------------------------------------------------- PDF assembly
class _Mark(Flowable):
    """Zero-size flowable that sets the footer label for the page it lands on (and later pages)."""

    def __init__(self, doc: "_AuditDoc", label: str):
        super().__init__()
        self._d, self._label = doc, label

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        self._d.current_label = self._label
        self._d.page_labels[self.canv.getPageNumber()] = self._label


BODY_H = PAGE_H - MARGIN - (MARGIN + 0.25 * inch) - 12 - 4  # usable frame height (frame padding + safety)


class _Block(Flowable):
    """Caption flowables followed by attachment content scaled to the page frame width.

    The content keeps its aspect ratio and is as wide as the frame (height-limited for tall content). If the space
    left on the current page holds it at >= ``min_ratio`` of that size it is shrunk to fit there, so an attachment
    can sit directly under the transaction details; otherwise the whole block moves to the next page.
    """

    def __init__(self, head: list, iw: float, ih: float, draw_fn, min_ratio: float = 0.6):
        super().__init__()
        self.head, self.iw, self.ih, self._draw_fn, self.min_ratio = head, max(iw, 1.0), max(ih, 1.0), draw_fn, min_ratio

    def wrap(self, aw, ah):
        self.hs = []
        hh = 0.0
        for f in self.head:
            _, h = f.wrap(aw, ah)
            sb, sa = f.getSpaceBefore(), f.getSpaceAfter()
            self.hs.append((f, h, sb, sa))
            hh += h + sb + sa
        s = min(aw / self.iw, (BODY_H - hh) / self.ih)
        fw, fh = self.iw * s, self.ih * s
        if hh + fh > ah and ah - hh >= fh * self.min_ratio:
            r = (ah - hh) / fh
            fw, fh = fw * r, fh * r
        self.aw, self.fw, self.fh, self.hh = aw, fw, fh, hh
        self.width, self.height = aw, hh + fh
        return self.width, self.height

    def drawOn(self, canvas, x, y, _sW=0):
        cur = y + self.height
        for f, h, sb, sa in self.hs:
            cur -= sb + h
            f.drawOn(canvas, x, cur)
            cur -= sa
        self._draw_fn(canvas, x + (self.aw - self.fw) / 2, y, self.fw, self.fh)


class _AuditDoc(SimpleDocTemplate):
    def __init__(self, buf, **kw):
        super().__init__(buf, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN,
                         bottomMargin=MARGIN + 0.25 * inch, **kw)
        self.current_label = ""
        self.page_labels: dict[int, str] = {}
        self.slots: list[tuple[int, float, float, float, float, object]] = []  # page, x, y, w, h, pypdf page

    def afterPage(self):
        self.page_labels.setdefault(self.page, self.current_label)


def _stamp_and_write(reader_bytes: bytes, doc: _AuditDoc, path: str, title: str) -> int:
    """Merges the reserved PDF-attachment slots (vector, scaled) and stamps footers."""
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(reader_bytes)))
    for page_no, x, y, w, h, src in doc.slots:
        box = src.cropbox
        sw, sh = float(box.width), float(box.height)
        s = min(w / sw, h / sh)
        op = (Transformation().translate(-float(box.left), -float(box.bottom)).scale(s, s)
              .translate(x + (w - sw * s) / 2, y + (h - sh * s) / 2))
        writer.pages[page_no - 1].merge_transformed_page(src, op, over=True)
    total = len(writer.pages)
    for i, page in enumerate(writer.pages):
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(w, h))
        c.setFont(_FONT, 7)
        c.setFillColor(colors.HexColor("#444444"))
        c.drawString(18, 10, f"{title}  ·  {doc.page_labels.get(i + 1, '')}"[:160])
        c.drawRightString(w - 18, 10, f"Page {i + 1} of {total}")
        c.save()
        buf.seek(0)
        page.merge_page(PdfReader(buf).pages[0])
    writer.add_metadata({"/Title": title, "/Producer": "Financial Management POC"})
    with open(path, "wb") as fh:
        writer.write(fh)
    return total


def _attachment_bytes(settings, a: Attachment) -> tuple[bytes | None, str]:
    try:
        with open(path_for(settings, a), "rb") as fh:
            data = fh.read()
    except OSError:
        return None, "stored file missing"
    if hashlib.sha256(data).hexdigest() != a.sha256:
        return data, "SHA-256 MISMATCH - stored file differs from the uploaded file"
    return data, "SHA-256 verified"


def _frame_box(canvas, x, y, w, h):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#c3c9d0"))
    canvas.setLineWidth(0.5)
    canvas.rect(x - 1, y - 1, w + 2, h + 2)
    canvas.restoreState()


def _attachment_flowables(doc: _AuditDoc, settings, a: Attachment, heading: str, users: dict[int, str]) -> list:
    """Caption line followed by the attachment's content rendered within the page width."""
    data, integrity = _attachment_bytes(settings, a)
    cap = PM(f"<b>{escape(heading)}</b> — {escape(a.original_filename)}", "h3")
    meta = P(f"{a.mime_type} · {a.size_bytes:,} bytes · uploaded {a.uploaded_at:%Y-%m-%d %H:%M} UTC by "
             f"{users.get(a.uploaded_by_user_id, '?')} · SHA-256 {a.sha256} ({integrity})", "small")
    head = [Spacer(1, 6), cap, meta, Spacer(1, 3)]
    if data is None:
        return head + [P(f"Attachment content unavailable: {integrity}.", "body")]
    if a.mime_type.startswith("image/"):
        try:
            with PILImage.open(io.BytesIO(data)) as im:
                iw, ih = im.size

            def draw_img(canvas, x, y, w, h, _d=data):
                canvas.drawImage(ImageReader(io.BytesIO(_d)), x, y, w, h, preserveAspectRatio=True, mask="auto")
                _frame_box(canvas, x, y, w, h)
            return [_Block(head, iw, ih, draw_img)]
        except Exception:
            return head + [P("Image could not be rendered.", "body")]
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("encrypted")
        pages = list(reader.pages)
        if not pages:
            raise ValueError("no pages")
        for p in pages:
            p.transfer_rotation_to_content()
            _ = p.cropbox.width  # validate the page box
    except Exception:
        return head + [P("This PDF could not be embedded (malformed or protected). The stored file is retained and "
                         "identified by its SHA-256 above.", "body")]
    out: list = []
    for n, p in enumerate(pages):
        def draw_pdf(canvas, x, y, w, h, _p=p):
            doc.slots.append((canvas.getPageNumber(), x, y, w, h, _p))
            _frame_box(canvas, x, y, w, h)
        pw, ph = float(p.cropbox.width), float(p.cropbox.height)
        if n == 0:
            out.append(_Block(head + ([P(f"Page 1 of {len(pages)}", "small")] if len(pages) > 1 else []), pw, ph, draw_pdf))
        else:
            out.append(_Block([Spacer(1, 6), P(f"{heading} — page {n + 1} of {len(pages)}", "small")], pw, ph, draw_pdf))
    return out


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
def _txn_description(t: RegisterTransaction) -> str:
    live = t.live_allocations
    descs = [a.description for a in live if a.description]
    if len(live) <= 1:
        return descs[0] if descs else "—"
    return "\n".join(f"{i + 1}. {a.description or '(no description)'} — {money(a.amount_cents)}" for i, a in enumerate(live))


def _meta_table(rows: list[tuple[str, object]]) -> Table:
    """The seven headline transaction fields, printed large at the top of each transaction page."""
    w1 = 1.55 * inch
    data = [[PM(f"<b>{escape(k)}</b>", "metak"), P(v, "metav")] for k, v in rows]
    t = Table(data, colWidths=[w1, FRAME_W - 12 - w1])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#6b7682")),
                           ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#c3c9d0")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef1f5")),
                           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _budget_section(tree: dict) -> list:
    f: list = [PM("Fiscal Year Budgets", "h1")]
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
            data.insert(1, [P(f"No {label.lower()} budgets.", "cell")] + [""] * (len(qn) + 4))
        f.append(_grid(data, [1.95 * inch, 1.0 * inch, 0.75 * inch] + [0.52 * inch] * len(qn) + [0.7 * inch, 0.72 * inch]))
        f.append(Spacer(1, 8))
    if tree["budget_zero"]:
        b0 = tree["budget_zero"]
        f.append(P(f"Protected Budget 0 (non-budget activity such as transfers between accounts): inflows "
                   f"{money(b0.get('inflow'))}, outflows {money(b0.get('outflow'))}.", "small"))
    return f


def _long_date(d: dt.date) -> str:
    return f"{d:%B} {d.day}, {d.year}"  # portable (no %-d on Windows)


def allocation_label(db: Session, t: RegisterTransaction, al: TransactionAllocation) -> str:
    """v1.3 CR-009: "<Entity> - <Budget>" (entity falls back to the transaction's; budget label as in the UI)."""
    from .register import _budget_info
    ent = al.entity if al.entity is not None else t.parent_entity
    budget = _budget_info(db, al.budget)["label"]
    return f"{ent.display_name} - {budget}" if ent is not None and not ent.is_system else budget


def _id_list(ids: list[int], limit: int = 60) -> str:
    s = ", ".join(f"#{i}" for i in ids[:limit])
    return s + (f" and {len(ids) - limit} more" if len(ids) > limit else "")


FY_DOC_LABELS = {"APPROVAL": "Approval document", "AUDIT_SIGNOFF": "Audit Signoff", "UNSPECIFIED": "Other document"}


def build_audit_report(db: Session, ctx, settings, fy: FiscalYear, account_id: int | None = None,
                       include_void: bool = True, layout: str = "audit") -> tuple[str, str, dict]:
    """Returns (temp file path, download filename, summary). Caller deletes the file.

    Layout "audit" (v1.2.1 CR-002; v1.3 Q5): page 1 title page; page 2 Fiscal Year Review introduction; pages 3-n
    budgets; then at least one page per transaction - the headline fields at the top and every attachment rendered
    underneath within the 8.5x11 page width.
    Layout "close" (v1.3 CR-008, Fiscal Year Close report): identical, with the Fiscal Year documents (Approval,
    Audit Signoff, other) inserted after the Fiscal Year Review and before the budgets and transactions.
    """
    close_layout = layout == "close"
    report_name = "Fiscal Year Close Report" if close_layout else "End of Year Audit Report"
    ws = db.get(Workspace, ctx.workspace_id)
    users = {u.id: u.username for u in db.scalars(select(User).where(User.workspace_id == ctx.workspace_id))}
    accts = {a.id: a for a in db.scalars(select(BankAccount).where(BankAccount.workspace_id == ctx.workspace_id))}
    if account_id is not None and account_id not in accts:
        raise validation("Bank Account not found.", "bank_account_id")
    title = f"{report_name} — {fy.display_name} — {ws.name}"
    buf = io.BytesIO()
    doc = _AuditDoc(buf, title=report_name, author=ws.name)
    tree = bsvc.tree(db, fy)
    check = closure_check(db, fy)
    txns = audit_transactions(db, ctx.workspace_id, fy, account_id, include_void)
    doc_review = documentation_review(db, fy)
    doc_items = {i["transaction_id"]: i for i in doc_review}
    fy_atts = list(db.scalars(select(Attachment).where(Attachment.fiscal_year_id == fy.id, Attachment.active.is_(True),
                                                       Attachment.system_generated.is_(False))
                              .order_by(Attachment.id)))
    order = {"APPROVAL": 0, "AUDIT_SIGNOFF": 1}
    fy_atts.sort(key=lambda a: (order.get(a.document_type or "UNSPECIFIED", 2), a.id))
    att_cache = {t.id: _attachments_for(db, t) for t in txns}
    now = utcnow()
    scope = (accts[account_id].account_name + " - " + bank.masked(accts[account_id]) if account_id
             else "All register-enabled accounts")

    # ---- page 1: title page
    f: list = [_Mark(doc, "Title"), Spacer(1, 1.6 * inch), PM(escape(ws.name), "cover_org"), Spacer(1, 10),
               PM(report_name, "cover_title"), Spacer(1, 6),
               PM(f"Fiscal Year {escape(fy.display_name)}", "cover_sub"),
               PM(f"{_long_date(fy.start_date)} – {_long_date(fy.end_date)}", "cover_sub"), Spacer(1, 1.2 * inch),
               _kv([("Fiscal Year status", fy.status.title()),
                    ("Approved", f"{fy.approved_at:%Y-%m-%d %H:%M} UTC by {users.get(fy.approved_by_user_id, '?')}"
                     if fy.approved_at else "—"),
                    ("Closed", f"{fy.closed_at:%Y-%m-%d %H:%M} UTC by {users.get(fy.closed_by_user_id, '?')}"
                     if fy.closed_at else "—"),
                    ("Accounts", scope),
                    ("Transactions", f"{len(txns)} ({'including' if include_void else 'excluding'} VOID)"),
                    ("Generated", f"{now:%Y-%m-%d %H:%M} UTC by {ctx.user.username}")], w1=1.6 * inch),
               PageBreak()]

    # ---- page 2: Fiscal Year Review introduction
    active = [t for t in txns if t.status == "ACTIVE"]
    dep = sum(t.total_cents for t in active if t.transaction_type == "DEPOSIT")
    wd = sum(t.total_cents for t in active if t.transaction_type == "WITHDRAWAL")
    n_att = sum(len(v[0]) + sum(len(x) for x in v[1].values()) for v in att_cache.values())
    missing = [i["transaction_id"] for i in doc_review if i["category"] == "MISSING_ATTACHMENTS"]
    marked = [i["transaction_id"] for i in doc_review if i["category"] == "NO_ATTACHMENT_MARKED"]
    in_report = {t.id for t in txns}
    per_acct: dict[int, list[int]] = {}
    for t in active:
        per_acct.setdefault(t.bank_account_id, [0, 0, 0])
        row = per_acct[t.bank_account_id]
        row[0] += 1
        row[1 if t.transaction_type == "DEPOSIT" else 2] += t.total_cents
    f += [_Mark(doc, "Fiscal Year Review"), PM("Fiscal Year Review", "h1"),
          P(f"This report documents Fiscal Year {fy.display_name} ({fy.start_date} to {fy.end_date}) for {ws.name}. "
            "It is organised as follows: this review summary; "
            + ("the Fiscal Year documents (approval, audit signoff and other supporting documents); the Fiscal Year "
               "budgets; " if close_layout else "the Fiscal Year budgets (page 3 onward); ")
            + "then every transaction of the year on its own page(s), with the transaction details at the top and each "
              "supporting attachment reproduced beneath them.", "body"),
          Spacer(1, 8), PM("Activity summary", "h2"),
          _kv([("Transactions", f"{len(txns)} in this report — {len(active)} active, {len(txns) - len(active)} VOID"),
               ("Deposits (active)", money(dep)), ("Withdrawals (active)", money(wd)), ("Net", money(dep - wd)),
               ("Attachments", f"{n_att} transaction/allocation attachment(s); {len(fy_atts)} Fiscal Year document(s)")])]
    if per_acct:
        data = [[PM(f"<b>{h}</b>", "cell") for h in ("Account", "Transactions", "Deposits", "Withdrawals")]]
        for aid, (n, d, w) in sorted(per_acct.items(), key=lambda kv: accts[kv[0]].account_name.lower()):
            a = accts[aid]
            data.append([P(f"{a.account_name} - {bank.masked(a)}", "cell"), P(n, "cellr"), P(money(d), "cellr"),
                         P(money(w), "cellr")])
        f += [Spacer(1, 4), _grid(data, [3.4 * inch, 1.0 * inch, 1.3 * inch, 1.3 * inch])]
    f += [Spacer(1, 8), PM("Closure readiness", "h2")]
    if fy.status == "CLOSED":
        items = [f"The Fiscal Year is closed ({fy.closed_at:%Y-%m-%d %H:%M} UTC by {users.get(fy.closed_by_user_id, '?')})."
                 if fy.closed_at else "The Fiscal Year is closed."]
    else:
        items = ([f"Blocker: {b['message']}" for b in check["blockers"]]
                 + [f"Warning: {w['message']}" for w in check["warnings"]])
    f += [P("• " + x, "body") for x in (items or ["No blockers or warnings."])]
    f += [Spacer(1, 8), PM("Documentation review", "h2"),
          P("A transaction is documented when it has an attachment or is marked 'no attachment will be provided'. "
            "When the transaction itself has neither, every allocation (child) must have an attachment or its own "
            "marker. These items are review warnings; they do not block closure.", "small"), Spacer(1, 2)]
    if not missing and not marked:
        f.append(P("• All applicable transactions are documented by attachments.", "body"))
    if missing:
        f.append(P(f"• Missing supporting attachments ({len(missing)}): {_id_list(missing)}", "body"))
    if marked:
        f.append(P(f"• Marked 'no attachment will be provided' ({len(marked)}): {_id_list(marked)}", "body"))
    outside = [i for i in missing + marked if i not in in_report]
    if outside:
        f.append(P(f"({len(outside)} of these are outside this report's account/VOID filter.)", "small"))
    f.append(PageBreak())

    # ---- Close report only: Fiscal Year documents before the budgets and transactions (v1.3 CR-008)
    if close_layout:
        f += [_Mark(doc, "Fiscal Year documents"), PM("Fiscal Year documents", "h1")]
        if fy.approval_no_attachment and not any(a.document_type == "APPROVAL" for a in fy_atts):
            f.append(P("Approval document: none — the Fiscal Year is marked as having no approval document"
                       + (f" ({fy.approval_no_attachment_reason})." if fy.approval_no_attachment_reason else "."), "body"))
        if not fy_atts:
            f.append(P("No Fiscal Year documents are attached.", "body"))
        counts: dict[str, int] = {}
        for x in fy_atts:
            counts[x.document_type or "UNSPECIFIED"] = counts.get(x.document_type or "UNSPECIFIED", 0) + 1
        seen: dict[str, int] = {}
        for x in fy_atts:
            kind = x.document_type or "UNSPECIFIED"
            seen[kind] = seen.get(kind, 0) + 1
            f += _attachment_flowables(doc, settings, x, f"{FY_DOC_LABELS[kind]} {seen[kind]} of {counts[kind]}", users)
        f.append(PageBreak())

    # ---- budgets
    f += [_Mark(doc, "Budgets")] + _budget_section(tree) + [PageBreak()]

    # ---- one or more pages per transaction
    if not txns:
        f += [_Mark(doc, "Transactions"), PM("Transactions", "h1"), P("No transactions for this Fiscal Year.", "body")]
    for t in txns:
        a = accts[t.bank_account_id]
        parent_atts, by_alloc, removed = att_cache[t.id]
        live = t.live_allocations
        void = t.status == "VOID"
        f += [_Mark(doc, f"Transaction #{t.id}"),
              PM(f"Transaction #{t.id}" + (" — <font color='#b3261e'>VOID</font>" if void else ""), "h1"),
              P(f"{a.account_name} - {bank.masked(a)}", "small"), Spacer(1, 4)]
        ent = t.parent_entity
        f.append(_meta_table([
            ("Transaction date", t.transaction_date),
            ("Entity", f"{ent.display_name} ({ent.entity_number})" if ent else "—"),
            ("Transaction type", t.transaction_type.title()),
            ("Amount", money(t.total_cents)),
            ("Description", _txn_description(t)),
            ("Clear Date", t.clear_date or "Uncleared"),
            ("Notes", t.notes or "—")]))
        extra = [("Status", t.status), ("Check number", t.check_number or "—"),
                 ("Entered", f"{t.entry_timestamp:%Y-%m-%d %H:%M} UTC by {users.get(t.created_by_user_id, '?')}")]
        if void:
            extra.append(("Void", f"{t.void_reason} — {t.voided_at:%Y-%m-%d %H:%M} UTC by "
                                  f"{users.get(t.voided_by_user_id, '?')}" if t.voided_at else t.void_reason))
        if t.transfer_group:
            other = db.scalar(select(RegisterTransaction).where(RegisterTransaction.transfer_group == t.transfer_group,
                                                                RegisterTransaction.id != t.id))
            if other is not None:
                oa = accts[other.bank_account_id]
                extra.append(("Transfer", f"{'to' if t.transaction_type == 'WITHDRAWAL' else 'from'} {oa.account_name} "
                                          f"{bank.masked(oa)} (transaction #{other.id})"))
        if t.no_attachment:
            extra.append(("Documentation", f"Marked 'no attachment will be provided': {t.no_attachment_reason or '(no reason)'}"))
        di = doc_items.get(t.id)
        if di and di["category"] == "MISSING_ATTACHMENTS":
            extra.append(("Documentation review", "WARNING: supporting attachments missing"))
        f += [Spacer(1, 4), _kv(extra, w1=1.2 * inch, style="small")]
        # allocations (budget detail) - compact
        rows = [[PM(f"<b>{h}</b>", "cell") for h in ("Budget", "Entity", "Invoice #", "Description / notes", "Docs",
                                                     "Amount")]]
        for al in live:
            b = al.budget
            parent = db.get(Budget, b.parent_budget_id) if b.parent_budget_id else None
            lbl = budget_label(parent, None) if b.is_other and parent and not bsvc.children_of(db, parent)[0] else budget_label(b, parent)
            fyb = db.get(FiscalYear, b.fiscal_year_id)
            revs = db.scalars(select(FiscalYearReview).where(FiscalYearReview.transaction_allocation_id == al.id)).all()
            desc = " — ".join(x for x in (al.description, al.notes) if x)
            if revs:
                desc += ("\n" if desc else "") + "Review: " + "; ".join(
                    f"{r.category} {r.status}" + (f" ({r.review_note})" if r.review_note else "") for r in revs)
            docs = (f"{len(by_alloc.get(al.id, []))} att." if by_alloc.get(al.id) else
                    ("No attachment" + (f": {al.no_attachment_reason}" if al.no_attachment_reason else "")
                     if al.no_attachment else "—"))
            rows.append([P(f"{fyb.display_name} / {lbl}", "cell"), P(al.entity.display_name if al.entity else "", "cell"),
                         P(al.invoice_number or "", "cell"), P(desc, "cell"), P(docs, "cell"),
                         P(money(al.amount_cents), "cellr")])
        f += [Spacer(1, 4), _grid(rows, [1.7 * inch, 1.1 * inch, 0.65 * inch, 2.05 * inch, 0.75 * inch, 0.8 * inch])]
        ordered: list[tuple[str, Attachment]] = [("transaction", x) for x in parent_atts]
        for al in live:
            ordered += [(allocation_label(db, t, al), x) for x in by_alloc.get(al.id, [])]
        if not ordered:
            f += [Spacer(1, 6), P("No attachments." + (" Marked 'no attachment will be provided'." if t.no_attachment
                                                       else ""), "small")]
        for i, (k, x) in enumerate(ordered):
            f += _attachment_flowables(doc, settings, x, f"Attachment {i + 1} of {len(ordered)} ({k})", users)
        if removed:
            f += [Spacer(1, 4), P("Removed attachments (retained in history, not reproduced): " + ", ".join(
                f"{x.original_filename} (removed {x.removed_at:%Y-%m-%d})" for x in removed), "small")]
        f.append(PageBreak())

    if f and isinstance(f[-1], PageBreak):
        f.pop()  # no blank page at the end
    doc.build(f)
    fd, path = tempfile.mkstemp(prefix="fmpoc-audit-", suffix=".pdf")
    os.close(fd)
    try:
        pages = _stamp_and_write(buf.getvalue(), doc, path, title)
    except Exception:
        os.unlink(path)
        raise
    fname = f"{fy.display_name}-{'fiscal-year-close' if close_layout else 'end-of-year-audit'}-report.pdf"
    return path, fname, {"transactions": len(txns), "pages": pages}


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
