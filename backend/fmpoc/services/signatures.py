"""v1.4.1 CR-016: audit review signature page (wording, variables, saved templates, signers)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..errors import conflict, not_found, validation
from ..models import Entity, FiscalYear, SignatureTemplate, Workspace

MAX_SAVED = 4
MAX_SIGNERS = 5
MAX_TEXT = 3000
MAX_TITLE = 60

DEFAULT_TEXT = (
    "We, the undersigned, have conducted an internal audit and inspection of the financial statements, ledgers, "
    "receipts, and bank statements of {ORG} for the fiscal year {FY}.\n\n"
    "We certify that, to the best of our knowledge, the submitted statements fairly represent, in all material "
    "respects, the financial position of {ORG} as of {FYE}. The records are hereby formally accepted and approved."
)

VARIABLES = {
    "FY": "Fiscal Year date range, e.g. July 1, 2025 – June 30, 2026",
    "ORG": "Organization name",
    "FYE": "Fiscal Year end date, e.g. June 30, 2026",
}
_TOKEN = re.compile(r"\{([^{}]*)\}")


def _long_date(d) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def normalize(text: str | None) -> str:
    """Trims, normalizes line endings and validates length and variables."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        raise validation("The wording is required.", "text")
    if len(t) > MAX_TEXT:
        raise validation(f"The wording may be at most {MAX_TEXT} characters.", "text")
    unknown = sorted({m.group(1) for m in _TOKEN.finditer(t) if m.group(1) not in VARIABLES})
    if unknown:
        names = ", ".join("{" + u + "}" for u in unknown)
        raise validation(f"Unknown variable(s): {names}. Available: {{FY}}, {{ORG}}, {{FYE}}.", "text")
    return t


def render(text: str, fy: FiscalYear, ws: Workspace) -> str:
    values = {"FY": f"{_long_date(fy.start_date)} – {_long_date(fy.end_date)}", "ORG": ws.name,
              "FYE": _long_date(fy.end_date)}
    return _TOKEN.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def _out(t: SignatureTemplate) -> dict:
    return {"id": t.id, "text": t.text, "builtin": False, "created_at": t.created_at.isoformat()}


def list_templates(db: Session, ws_id: int) -> dict:
    saved = list(db.scalars(select(SignatureTemplate).where(SignatureTemplate.workspace_id == ws_id)
                            .order_by(SignatureTemplate.id)))
    return {"default": {"id": "default", "text": DEFAULT_TEXT, "builtin": True},
            "saved": [_out(t) for t in saved], "max_saved": MAX_SAVED, "variables": VARIABLES,
            "max_signers": MAX_SIGNERS}


def save_template(db: Session, ctx, text: str) -> dict:
    t = normalize(text)
    existing = db.scalar(select(SignatureTemplate).where(SignatureTemplate.workspace_id == ctx.workspace_id,
                                                         SignatureTemplate.text == t))
    if existing is not None:
        return _out(existing)
    if t == DEFAULT_TEXT:
        raise conflict("SIGNATURE_TEMPLATE_IS_DEFAULT", "This is the built-in default wording; it is always available.")
    n = db.scalar(select(func.count(SignatureTemplate.id)).where(SignatureTemplate.workspace_id == ctx.workspace_id)) or 0
    if n >= MAX_SAVED:
        raise conflict("SIGNATURE_TEMPLATE_LIMIT",
                       f"Only {MAX_SAVED} wordings can be saved. Delete one of the saved wordings first.")
    row = SignatureTemplate(workspace_id=ctx.workspace_id, text=t, created_by_user_id=ctx.user.id)
    db.add(row)
    db.flush()
    audit.record(db, ctx, "SIGNATURE_TEMPLATE_SAVED", "signature_template", row.id, None, {"text": t})
    db.commit()
    return _out(row)


def delete_template(db: Session, ctx, template_id: int) -> None:
    row = db.get(SignatureTemplate, template_id)
    if row is None or row.workspace_id != ctx.workspace_id:
        raise not_found("Saved wording")
    audit.record(db, ctx, "SIGNATURE_TEMPLATE_DELETED", "signature_template", row.id, {"text": row.text}, None)
    db.delete(row)
    db.commit()


@dataclass(frozen=True)
class SignaturePage:
    text: str  # rendered (variables replaced)
    signers: list[tuple[str, str | None]]  # (name, title)
    source: str  # "default" | "saved:<id>" | "custom"


def resolve(db: Session, ctx, fy: FiscalYear, ws: Workspace, template_id: str | None, text: str | None,
            signer_ids: list[int], signer_titles: list[str]) -> SignaturePage:
    if text not in (None, ""):
        raw, source = normalize(text), "custom"
    elif template_id in (None, "", "default"):
        raw, source = DEFAULT_TEXT, "default"
    else:
        try:
            tid = int(template_id)
        except ValueError:
            raise validation("Unknown saved wording.", "signature_template_id") from None
        row = db.get(SignatureTemplate, tid)
        if row is None or row.workspace_id != ctx.workspace_id:
            raise validation("Unknown saved wording.", "signature_template_id")
        raw, source = row.text, f"saved:{row.id}"
    return SignaturePage(render(raw, fy, ws), resolve_signers(db, ctx, signer_ids, signer_titles), source)


def resolve_signers(db: Session, ctx, signer_ids: list[int], signer_titles: list[str]) -> list[tuple[str, str | None]]:
    """0-5 distinct active individual Entities with optional titles (also used by the cash count sheet, CR-038)."""
    if len(signer_ids) > MAX_SIGNERS:
        raise validation(f"At most {MAX_SIGNERS} signers can be listed.", "signer_id")
    if len(set(signer_ids)) != len(signer_ids):
        raise validation("Each signer can be listed only once.", "signer_id")
    if len(signer_titles) > len(signer_ids):
        raise validation("A title was given without a signer.", "signer_title")
    signers: list[tuple[str, str | None]] = []
    for i, eid in enumerate(signer_ids):
        e = db.get(Entity, eid)
        if (e is None or e.workspace_id != ctx.workspace_id or not e.active or e.is_system
                or e.entity_type != "INDIVIDUAL"):
            raise validation("Signers must be active individual Entities.", "signer_id")
        title = (signer_titles[i] if i < len(signer_titles) else "").strip() or None
        if title and len(title) > MAX_TITLE:
            raise validation(f"A signer title may be at most {MAX_TITLE} characters.", "signer_title")
        signers.append((e.display_name, title))
    return signers
