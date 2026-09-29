"""v1.3 CR-007 (Fiscal Year document types) and CR-008 (Fiscal Year Close report)."""
import io

from conftest import PDF_BYTES
from pypdf import PdfReader
from reportlab.pdfgen import canvas


def pdf(marker):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 700, marker)
    c.showPage()
    c.save()
    return buf.getvalue()


def upload(env, fy, dtype, name, data, client=None):
    c = client or env.bm
    return c.c.post(f"/api/attachments?owner_type=fiscal_year&owner_id={fy}" + (f"&document_type={dtype}" if dtype else ""),
                    files={"file": (name, data)}, headers={"X-CSRF-Token": c.csrf})


def texts(content):
    return [" ".join((p.extract_text() or "").split()) for p in PdfReader(io.BytesIO(content)).pages]


def test_cr007_document_types_and_retype(env, base):
    fy = base["fy"]["id"]
    r = upload(env, fy, None, "misc.pdf", PDF_BYTES)
    assert r.status_code == 201 and r.json()["document_type"] == "UNSPECIFIED"
    assert upload(env, fy, "BOGUS", "x.pdf", PDF_BYTES).status_code == 422
    # document_type is only for Fiscal Year attachments
    t = env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "1.00"}])
    rr = env.ru.c.post(f"/api/attachments?owner_type=transaction&owner_id={t['id']}&document_type=APPROVAL",
                       files={"file": ("x.pdf", PDF_BYTES)}, headers={"X-CSRF-Token": env.ru.csrf})
    assert rr.status_code == 422
    # retype (Budget Manager only), audited
    aid = r.json()["id"]
    assert env.bu.post(f"/api/attachments/{aid}/document-type", {"document_type": "AUDIT_SIGNOFF"}).status_code == 403
    assert env.ru.post(f"/api/attachments/{aid}/document-type", {"document_type": "AUDIT_SIGNOFF"}).status_code == 403
    assert env.bm.c.post(f"/api/attachments/{aid}/document-type", json={"document_type": "AUDIT_SIGNOFF"}).status_code == 403
    r2 = env.bm.post(f"/api/attachments/{aid}/document-type", {"document_type": "AUDIT_SIGNOFF"})
    assert r2.status_code == 200 and r2.json()["document_type"] == "AUDIT_SIGNOFF"
    assert env.bm.post(f"/api/attachments/{aid}/document-type", {"document_type": "AUDIT_SIGNOFF"}).status_code == 409
    assert env.bm.post(f"/api/attachments/{aid}/document-type", {"document_type": "NOPE"}).status_code == 422
    ev = env.auditor.get(f"/api/audit-events?action=ATTACHMENT_TYPE_CHANGED&object_id={aid}").json()["items"][0]
    assert ev["before"]["document_type"] == "UNSPECIFIED" and ev["after"]["document_type"] == "AUDIT_SIGNOFF"
    assert "AUDIT_SIGNOFF" not in {w["code"] for w in env.bm.get(f"/api/fiscal-years/{fy}/closure-check").json()["blockers"]}


def test_cr007_approval_no_attachment_mark(env, base):
    fy = base["fy"]["id"]
    url = f"/api/fiscal-years/{fy}/approval-no-attachment"
    assert env.bu.post(url, {"no_attachment": True}).status_code == 403
    r = env.bm.post(url, {"no_attachment": True, "reason": "Board approves verbally"})
    assert r.status_code == 200 and r.json()["approval_no_attachment"] is True
    # approval allowed with the mark; the confirmation lists the warning
    r = env.bm.post(f"/api/fiscal-years/{fy}/approve", {"confirm_irreversible": False})
    assert "APPROVAL_NO_ATTACHMENT" in {w["code"] for w in r.json()["error"]["warnings"]}
    assert env.bm.post(f"/api/fiscal-years/{fy}/approve", {"confirm_irreversible": True}).status_code == 200
    chk = env.bm.get(f"/api/fiscal-years/{fy}/closure-check").json()
    assert "APPROVAL_NO_ATTACHMENT" in {w["code"] for w in chk["warnings"]}
    assert "APPROVAL_DOCUMENT_MISSING" not in {b["code"] for b in chk["blockers"]}
    # uploading an approval document later clears the mark automatically (audited)
    assert upload(env, fy, "APPROVAL", "minutes.pdf", PDF_BYTES).status_code == 201
    assert env.bm.get(f"/api/fiscal-years/{fy}").json()["approval_no_attachment"] is False
    assert env.auditor.get("/api/audit-events?action=FY_APPROVAL_NO_ATTACHMENT_CLEARED").json()["total"] == 1
    # with an approval document present the mark cannot be set
    assert env.bm.post(url, {"no_attachment": True}).status_code == 409


def test_cr007_retype_clears_mark_and_closed_fy_is_frozen(env, base):
    fy = base["fy"]["id"]
    env.bm.post(f"/api/fiscal-years/{fy}/approval-no-attachment", {"no_attachment": True})
    env.bm.post(f"/api/fiscal-years/{fy}/approve", {"confirm_irreversible": True})
    doc = upload(env, fy, None, "minutes.pdf", PDF_BYTES).json()
    env.bm.post(f"/api/attachments/{doc['id']}/document-type", {"document_type": "APPROVAL"})
    assert env.bm.get(f"/api/fiscal-years/{fy}").json()["approval_no_attachment"] is False
    env.fy_doc(fy, "AUDIT_SIGNOFF")
    assert env.bm.post(f"/api/fiscal-years/{fy}/close", {"confirm_reviewed": True}).status_code == 200
    assert env.bm.post(f"/api/attachments/{doc['id']}/document-type", {"document_type": "UNSPECIFIED"}).status_code == 409
    assert env.bm.post(f"/api/fiscal-years/{fy}/approval-no-attachment", {"no_attachment": True}).status_code == 409


def test_cr008_close_report_saved_at_closing(env, base):
    fy = base["fy"]["id"]
    t = env.txn(base["acct"]["id"], "WITHDRAWAL", [{"budget_id": base["exp_leaf"], "amount": "12.00",
                                                    "description": "Rent"}], clear_date="2026-08-02")
    upload(env, fy, "APPROVAL", "approval.pdf", pdf("APPROVALDOC"))
    env.bm.post(f"/api/fiscal-years/{fy}/approve", {"confirm_irreversible": True})
    upload(env, fy, "AUDIT_SIGNOFF", "signoff.pdf", pdf("SIGNOFFDOC"))
    upload(env, fy, "UNSPECIFIED", "bank.pdf", pdf("OTHERDOC"))
    # on-demand close report: FY documents after the review, before budgets and transactions
    r = env.auditor.get(f"/api/reports/fy-close?fiscal_year_id={fy}")
    assert r.status_code == 200 and "fiscal-year-close-report.pdf" in r.headers["content-disposition"]
    pages = texts(r.content)
    assert "Fiscal Year Close Report" in pages[0] and "Fiscal Year Review" in pages[1]

    def at(s):
        return next(i for i, p in enumerate(pages) if s in p)
    assert 1 < at("APPROVALDOC") < at("SIGNOFFDOC") < at("OTHERDOC") < at("Fiscal Year Budgets") < at(f"Transaction #{t['id']}")
    assert "Approval document 1 of 1" in pages[at("APPROVALDOC")] and "Audit Signoff 1 of 1" in pages[at("SIGNOFFDOC")]
    assert env.admin.get(f"/api/reports/fy-close?fiscal_year_id={fy}").status_code == 403
    # the audit report does not contain the FY documents
    audit_pages = " ".join(texts(env.auditor.get(f"/api/reports/audit?fiscal_year_id={fy}").content))
    assert "SIGNOFFDOC" not in audit_pages and "End of Year Audit Report" in audit_pages
    # closing stores the Close report as a permanent, system-generated FY document
    assert env.bm.post(f"/api/fiscal-years/{fy}/close", {"confirm_reviewed": True}).status_code == 200
    atts = env.bm.get(f"/api/attachments?owner_type=fiscal_year&owner_id={fy}").json()
    rep = [a for a in atts if a["system_generated"]]
    assert len(rep) == 1 and rep[0]["document_type"] == "CLOSE_REPORT" and rep[0]["mime_type"] == "application/pdf"
    stored = texts(env.bu.get(rep[0]["content_url"]).content)
    assert "Fiscal Year Close Report" in stored[0] and "The Fiscal Year is closed" in stored[1]
    assert any("SIGNOFFDOC" in p for p in stored)
    assert env.bm.post(f"/api/attachments/{rep[0]['id']}/remove").status_code == 409
    # a later on-demand Close report does not include the stored copy of itself
    again = texts(env.bu.get(f"/api/reports/fy-close?fiscal_year_id={fy}").content)
    assert len(again) == len(stored)


def test_cr008_close_rolls_back_if_report_fails(env, base, monkeypatch):
    fy = base["fy"]["id"]
    env.approve(fy)
    env.fy_doc(fy, "AUDIT_SIGNOFF")
    from fmpoc.services import reports

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(reports, "build_audit_report", boom)
    r = env.bm.post(f"/api/fiscal-years/{fy}/close", {"confirm_reviewed": True})
    assert r.status_code == 500
    assert env.bm.get(f"/api/fiscal-years/{fy}").json()["status"] == "APPROVED"
